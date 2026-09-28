"""Pruebas del cobro. Lo que se protege aqui es que nadie pague dos veces y que
lo cobrado cuadre con lo calculado — Stripe va simulado, no se llama a la red.
"""
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock, skipUnless

import stripe
from stripe import StripeClient
from django.core.management import call_command
from django.db import connection
from django.db.utils import DatabaseError
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import (
    CUPO_MAXIMO_DEFAULT,
    Orden,
    Reserva,
    ReservaPersonalizacion,
    ReservaOcupacion,
    ReservaPaqueteComponente,
)
from apps.fleet.models import (
    CodigoPromocional,
    Paquete,
    PaqueteServicio,
    Recurso,
    Servicio,
)
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import crear_personalizacion_pesca, ApiTestCase, EmpresaTestCase, crear_flota, crear_servicio_pesca


from .checks import revisar_llaves_de_stripe
from .services import (
    APLICADO,
    SIN_CUPO_REEMBOLSADO,
    _reserva_del_cargo,
    aplicar_pago_exitoso,
    reembolsar,
)
from .stripe_client import configurar_stripe
from .views import (
    CrearPagoView,
    EstadoReservaView,
    PagoEnCurso,
    StripeWebhookView,
    ValidarCodigoPromocionalView,
)
from .pricing import (
    PERSONAS_INCLUIDAS,
    a_centavos,
    cargo_personalizacion,
    cargo_por_personas,
    de_centavos,
    monto_inicial,
    monto_por_empresa,
    personas_extra,
)

# Sigue usado por otras clases de este archivo (CrearPagoTests y hermanas) que
# todavia leen las llaves de settings, no de Empresa -- las retrofitea P5/P6.
# No lo consume RevisarLlavesDeStripeTests (ese check ya lee Empresa).
LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}


class RevisarLlavesDeStripeTests(TestCase):
    """Check de arranque que detecta una llave de Stripe puesta en el campo
    equivocado, ahora por fila de Empresa en vez de por variable de entorno.

    Nace de un caso real en produccion: en Render quedo el signing secret del
    webhook (`whsec_...`) dentro de `STRIPE_SECRET_KEY`. Con una Empresa por
    marca, cada una trae sus propias llaves en su propia fila — el check
    revisa cada una por separado y el mensaje identifica cual.
    """

    def setUp(self):
        # Slug distinto de 'la-paz' -- ya existe, sembrado por
        # tenancy.0002_crear_sede_empresa_la_paz (ver apps/testing.py).
        self.sede = Sede.objects.create(
            nombre='Sede stripe test', slug='sede-stripe-test', zona_horaria='America/Mazatlan',
        )

    def _crear_empresa(self, slug, secreta='sk_test_ok', webhook='whsec_ok'):
        return Empresa.objects.create(
            sede=self.sede, nombre=slug, slug=slug,
            stripe_secret_key=secreta, stripe_webhook_secret=webhook,
            stripe_publishable_key='pk_test_ok',
        )

    def test_llaves_correctas_no_reportan_nada(self):
        self._crear_empresa('sal-y-sol-2')
        self.assertEqual(revisar_llaves_de_stripe(None), [])

    def test_llaves_vacias_no_reportan_nada(self):
        # Vacio significa "Stripe apagado para esta Empresa", comportamiento
        # documentado (crear-pago responde 503), no una llave cruzada.
        self._crear_empresa('sin-stripe', secreta='', webhook='')
        self.assertEqual(revisar_llaves_de_stripe(None), [])

    def test_el_signing_secret_dentro_de_la_llave_secreta(self):
        self._crear_empresa('sal-y-sol-2', secreta='whsec_falsa', webhook='whsec_ok')
        errores = revisar_llaves_de_stripe(None)
        self.assertEqual([e.id for e in errores], ['payments.E001'])
        self.assertIn('sal-y-sol-2', errores[0].msg)

    def test_la_llave_secreta_dentro_del_signing_secret(self):
        self._crear_empresa('sal-y-sol-2', secreta='sk_test_ok', webhook='sk_test_falsa')
        errores = revisar_llaves_de_stripe(None)
        self.assertEqual([e.id for e in errores], ['payments.E002'])

    def test_dos_empresas_cada_una_reporta_la_suya(self):
        self._crear_empresa('cruzada', secreta='whsec_falsa')
        self._crear_empresa('correcta')
        errores = revisar_llaves_de_stripe(None)
        self.assertEqual(len(errores), 1)
        self.assertIn('cruzada', errores[0].msg)

    def test_el_mensaje_no_incluye_el_valor_de_la_llave(self):
        self._crear_empresa('sal-y-sol-2', secreta='whsec_secretisimo')
        texto = ' '.join(f'{e.msg} {e.hint}' for e in revisar_llaves_de_stripe(None))
        self.assertNotIn('secretisimo', texto)

    def test_tabla_inexistente_no_revienta(self):
        # Ventana entre que corre collectstatic/migrate y que tenancy.0001
        # crea la tabla — el check debe callar, no tronar el deploy.
        with mock.patch(
            'apps.tenancy.models.Empresa.objects.all',
            side_effect=DatabaseError('relation "tenancy_empresa" does not exist'),
        ):
            self.assertEqual(revisar_llaves_de_stripe(None), [])


CHECKOUT_ID = '11111111-1111-4111-8111-111111111111'


def crear_reserva(empresa, **overrides):
    empresa_real = overrides.get('empresa', empresa)
    crear_flota(empresa_real)  # el motor de cupo le pregunta a la flota; sin pangas no cabe nadie
    datos = {
        'empresa': empresa_real,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        # Como en produccion: una reserva web trae el identificador que genero el
        # navegador, y es lo que acredita al dueño del checkout frente a
        # `crear-pago`. Sin esto los tests cobrarian por una puerta que la web
        # real no usa.
        'checkout_id': CHECKOUT_ID,
    }
    if 'servicio' not in overrides and 'paquete' not in overrides:
        datos['servicio'] = crear_servicio_pesca(empresa_real)
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva


def intent_falso(id='pi_1', amount=450000, status='requires_payment_method', currency='mxn'):
    return mock.Mock(id=id, amount=amount, currency=currency, status=status, client_secret=f'{id}_secret')


def evento_pagado(reserva_id, intent_id='pi_1', amount=450000, currency='mxn'):
    return {
        'id': 'evt_1',
        'type': 'payment_intent.succeeded',
        'data': {'object': {
            'id': intent_id,
            'amount_received': amount,
            'currency': currency,
            'metadata': {'reserva_id': str(reserva_id)},
        }},
    }


class PricingTests(TestCase):
    def test_anticipo_es_el_30_por_ciento(self):
        self.assertEqual(monto_inicial(Decimal('4500.00'), 'anticipo'), Decimal('1350.00'))

    def test_completo_es_el_total(self):
        self.assertEqual(monto_inicial(Decimal('4500.00'), 'completo'), Decimal('4500.00'))

    def test_anticipo_redondea_a_centavos(self):
        # 4525 * 0.30 = 1357.5 exacto; con amenidades impares aparecen los medios.
        self.assertEqual(monto_inicial(Decimal('4525.00'), 'anticipo'), Decimal('1357.50'))

    def test_ida_y_vuelta_a_centavos(self):
        self.assertEqual(a_centavos(Decimal('1357.50')), 135750)
        self.assertEqual(de_centavos(135750), Decimal('1357.50'))

    def test_hasta_las_personas_incluidas_no_hay_cargo(self):
        for personas in range(1, PERSONAS_INCLUIDAS + 1):
            self.assertEqual(personas_extra(personas), 0)
            self.assertEqual(cargo_por_personas(Decimal('500'), personas), 0)

    def test_cobra_por_cada_persona_de_mas(self):
        self.assertEqual(cargo_por_personas(Decimal('500'), PERSONAS_INCLUIDAS + 1), 500)
        self.assertEqual(cargo_por_personas(Decimal('500'), 6), Decimal('1500'))

    def test_extra_por_persona_cobra_segun_cuantos_van(self):
        self.assertEqual(cargo_personalizacion(Decimal('150'), cobrar_por_persona=True, cantidad_editable=False, personas=1), Decimal('150'))
        self.assertEqual(cargo_personalizacion(Decimal('150'), cobrar_por_persona=True, cantidad_editable=False, personas=4), Decimal('600'))

    def test_extra_plano_no_multiplica_por_personas(self):
        self.assertEqual(cargo_personalizacion(Decimal('400'), cobrar_por_persona=False, cantidad_editable=False, personas=5), Decimal('400'))

    def test_extra_sin_precio_en_la_moneda_es_none(self):
        self.assertIsNone(cargo_personalizacion(None, cobrar_por_persona=True, cantidad_editable=False, personas=3))


@override_settings(**LLAVES)
class CrearPagoTests(ApiTestCase):
    def setUp(self):
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])
        self.servicio = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'), precio_base_usd=Decimal('260.00'),
            precio_persona_extra=Decimal('500.00'), precio_persona_extra_usd=Decimal('30.00'),
        )
        self.reserva = crear_reserva(self.empresa, servicio=self.servicio)
        self.url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': self.reserva.pk})

    def post(self, **body):
        datos = {'forma_pago': 'completo', 'checkout_id': str(self.reserva.checkout_id)}
        datos.update(body)
        return self.client.post(self.url, datos, content_type='application/json')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_reserva_sin_producto_rechaza_pago_sin_llamar_stripe(self, payment_intents):
        # Simula una fila inválida creada sin full_clean por una integración.
        Reserva.objects.filter(pk=self.reserva.pk).update(servicio=None, paquete=None)
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'],
                         'La reserva no tiene servicio ni paquete configurado.')
        payment_intents.create.assert_not_called()
        payment_intents.update.assert_not_called()
        self.reserva.refresh_from_db()
        self.assertFalse(self.reserva.stripe_payment_intent_id)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_precio_base_y_recargo_vigentes_del_servicio_en_ambas_monedas(self, payment_intents):
        self.servicio.precio_base = Decimal('5100')
        self.servicio.precio_base_usd = Decimal('300')
        self.servicio.precio_persona_extra = Decimal('600')
        self.servicio.precio_persona_extra_usd = Decimal('35')
        self.servicio.save()
        for moneda, personas, esperado in (
            ('MXN', 3, '5100.00'), ('MXN', 5, '6300.00'),
            ('USD', 3, '300.00'), ('USD', 5, '370.00'),
        ):
            with self.subTest(moneda=moneda, personas=personas):
                reserva = crear_reserva(self.empresa, servicio=self.servicio,
                                        moneda=moneda, numero_personas=personas,
                                        checkout_id=uuid.uuid4())
                payment_intents.create.return_value = intent_falso(
                    id=f'pi_{reserva.pk}', amount=a_centavos(Decimal(esperado)),
                    currency=moneda.lower())
                response = self.client.post(
                    reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
                    {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
                    content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['monto_a_cobrar'], esperado)
                self.assertEqual(payment_intents.create.call_args.args[0]['amount'],
                                 a_centavos(Decimal(esperado)))

    def seleccionar_extra(self, reserva=None, cantidad_solicitada=None, **overrides):
        """Simula lo que deja el checkout: la SELECCION de un extra, sin precio
        congelado todavia (eso solo lo escribe `CrearPagoView`). `cantidad_solicitada`
        es de la seleccion (`ReservaPersonalizacion`), no del catalogo — se separa aparte."""
        datos = {
            'empresa': self.empresa,
            'tipo': 'brunch', 'nombre': 'Brunch', 'precio': Decimal('300'),
            'precio_usd': Decimal('18'), 'cobrar_por_persona': True,
        }
        datos.update(overrides)
        reserva = reserva or self.reserva
        reserva.refresh_from_db()
        item = crear_personalizacion_pesca(servicio=reserva.servicio, **datos)
        return ReservaPersonalizacion.objects.create(
            reserva=reserva, servicio_personalizacion=item,
            cantidad=cantidad_solicitada if cantidad_solicitada is not None else reserva.numero_personas,
        )

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cobra_lo_que_calcula_el_servidor_no_lo_que_manda_el_cliente(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        # El cliente intenta colar su propio total y sus propios extras.
        response = self.post(precio_total='1.00', total=1, lleva_lunch=True, amenities=['lunch'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment_intents.create.call_args.args[0]['amount'], a_centavos(Decimal('4500.00')))
        self.assertEqual(response.json()['monto_a_cobrar'], '4500.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_anticipo_cobra_el_30_por_ciento(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        response = self.post(forma_pago='anticipo')

        self.assertEqual(payment_intents.create.call_args.args[0]['amount'], 135000)
        self.assertEqual(response.json()['monto_a_cobrar'], '1350.00')
        # El total completo queda guardado: el 70% se cobra en efectivo.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.precio_total, Decimal('4500.00'))
        self.assertEqual(self.reserva.saldo_pendiente, Decimal('4500.00'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_servicio_por_noche_multiplica_noches(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        servicio_hotel = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel Cabaña',
            slug='hotel-cabana',
            tipo_servicio='hospedaje',
            estrategia_precio='por_noche',
            precio_base=Decimal('1500.00'),
            porcentaje_anticipo=50,
        )
        reserva_hotel = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_hotel,
            fecha=date(2026, 10, 1),
            fecha_salida=date(2026, 10, 4),  # 3 noches
            hora=time(7, 0),
            numero_personas=2,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@test.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
        )
        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva_hotel.pk})
        # Anticipo: 3 noches * 1500 = 4500. Anticipo 50% = 2250.00
        resp = self.client.post(url, {
            'forma_pago': 'anticipo',
            'checkout_id': str(reserva_hotel.checkout_id),
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['monto_a_cobrar'], '2250.00')
        reserva_hotel.refresh_from_db()
        self.assertEqual(reserva_hotel.precio_total, Decimal('4500.00'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_paquete_sin_anticipo_cobra_pago_completo(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        paquete = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Super Paquete',
            slug='super-paquete',
            precio_ancla=Decimal('10000.00'),
            permite_anticipo=False,
        )
        reserva_paquete = Reserva.objects.create(
            empresa=self.empresa,
            paquete=paquete,
            fecha=date(2026, 10, 1),
            hora=time(7, 0),
            numero_personas=2,
            nombre_cliente='Ana Gomez',
            telefono_cliente='1234567890',
            correo_cliente='ana@test.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
        )
        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva_paquete.pk})
        # Pago completo cobra el total (10000.00)
        resp = self.client.post(url, {
            'forma_pago': 'completo',
            'checkout_id': str(reserva_paquete.checkout_id),
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['monto_a_cobrar'], '10000.00')
        reserva_paquete.refresh_from_db()
        self.assertEqual(reserva_paquete.precio_total, Decimal('10000.00'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_paquete_no_suma_extras_legacy(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        paquete = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Sin Extras Legacy',
            slug='paquete-sin-extras-legacy',
            precio_ancla=Decimal('5000.00'),
            porcentaje_anticipo=30,
        )
        reserva_paquete = Reserva.objects.create(
            empresa=self.empresa,
            paquete=paquete,
            fecha=date(2026, 10, 1),
            hora=time(7, 0),
            numero_personas=2,
            nombre_cliente='Carlos',
            telefono_cliente='1234567890',
            correo_cliente='carlos@test.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
        )
        # Asociar extra legacy
        self.seleccionar_extra(reserva=reserva_paquete)

        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva_paquete.pk})
        resp = self.client.post(url, {
            'forma_pago': 'completo',
            'checkout_id': str(reserva_paquete.checkout_id),
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        # Solo debe cobrar el ancla del paquete (5000.00), no los extras legacy
        self.assertEqual(resp.json()['monto_a_cobrar'], '5000.00')
        reserva_paquete.refresh_from_db()
        self.assertEqual(reserva_paquete.precio_total, Decimal('5000.00'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_hasta_3_personas_el_precio_no_cambia(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        for personas in (1, 2, 3):
            # Se limpia el intent para que cada vuelta sea un checkout nuevo y no
            # entre por la rama que reusa el intent anterior.
            Reserva.objects.filter(pk=self.reserva.pk).update(
                numero_personas=personas, stripe_payment_intent_id=''
            )
            self.assertEqual(self.post().json()['monto_a_cobrar'], '4500.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cobra_500_por_cada_persona_arriba_de_3(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        # 5 es el tope de la flota (MAX_PERSONAS): la panga mas grande lleva 5.
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        # 4500 del viaje + 2 personas extra x 500.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '5500.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_cargo_por_personas_sale_de_la_reserva_no_del_cliente(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        # Aunque el cliente insista en que van 2, se cobra por las 5 reservadas.
        self.assertEqual(self.post(numero_personas=2).json()['monto_a_cobrar'], '5500.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_anticipo_incluye_el_cargo_por_personas(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        # 30% de 5500.
        self.assertEqual(self.post(forma_pago='anticipo').json()['monto_a_cobrar'], '1650.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_brunch_se_cobra_por_cada_persona(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=4)
        self.seleccionar_extra()
        # 4500 del viaje + 1 persona extra x 500 + 4 brunches x 300.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '6200.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cantidad_editable_cobra_solo_lo_que_el_cliente_pidio(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        self.seleccionar_extra(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cantidad_editable=True, cantidad_solicitada=2,
        )
        # 4500 + 2 personas extra x 500 + 2 licencias x 450 (no 5).
        response = self.post()

        self.assertEqual(response.json()['monto_a_cobrar'], '6400.00')
        extra = ReservaPersonalizacion.objects.get(reserva=self.reserva)
        self.assertEqual(extra.cantidad, 2)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cantidad_editable_se_acota_al_grupo_nunca_cobra_de_mas(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        # El cliente eligio "5" antes de bajar el grupo a 2: nunca debe cobrar
        # licencia para mas personas de las que trae la reserva.
        self.seleccionar_extra(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cantidad_editable=True, cantidad_solicitada=5,
        )
        response = self.post()

        # 4500 + 2 licencias x 450 (acotado a numero_personas=2, no 5).
        self.assertEqual(response.json()['monto_a_cobrar'], '5400.00')
        extra = ReservaPersonalizacion.objects.get(reserva=self.reserva)
        self.assertEqual(extra.cantidad, 2)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_cantidad_solicitada_cantidad_editable_cobra_todo_el_grupo(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=4)
        self.seleccionar_extra(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cantidad_editable=True,
        )
        # Sin cantidad_solicitada (None): mismo comportamiento de siempre, todo el grupo.
        # 4500 + 1 persona extra x 500 + 4 licencias x 450.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '6800.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_bebidas_no_suma(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(pide_bebidas=True)
        # Bebidas la cotiza el agente aparte, no cambia el cobro.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '4500.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_precio_de_extra_en_dolares_no_se_cobra_a_medias(self, payment_intents):
        reserva = crear_reserva(self.empresa, moneda='USD')
        self.seleccionar_extra(reserva=reserva, precio=Decimal('300'), precio_usd=None)
        response = self.client.post(
            reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
            {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_congela_el_precio_vigente_del_catalogo_no_el_de_cuando_se_selecciono(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        seleccion = self.seleccionar_extra(precio=Decimal('300'), precio_usd=Decimal('18'))
        # El precio de lista cambia despues de que el cliente eligio, antes de pagar.
        seleccion.servicio_personalizacion.precio = Decimal('500')
        seleccion.servicio_personalizacion.save(update_fields=['precio'])

        response = self.post()

        # 4500 + 2 personas x 500 (el precio vigente, no los 300 de cuando eligio).
        self.assertEqual(response.json()['monto_a_cobrar'], '5500.00')
        seleccion.refresh_from_db()
        self.assertEqual(seleccion.precio_unitario, Decimal('500'))
        self.assertEqual(seleccion.cantidad, 2)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_un_extra_desactivado_se_cae_sin_bloquear_los_demas(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        activo = self.seleccionar_extra(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cobrar_por_persona=False,
        )
        a_caer = self.seleccionar_extra(precio=Decimal('300'), precio_usd=Decimal('18'))
        a_caer.servicio_personalizacion.activo = False
        a_caer.servicio_personalizacion.save(update_fields=['activo'])

        response = self.post()

        self.assertEqual(response.status_code, 200)
        # Solo la licencia entra al cobro: 4500 + 450.
        self.assertEqual(response.json()['monto_a_cobrar'], '4950.00')
        self.assertFalse(ReservaPersonalizacion.objects.filter(pk=a_caer.pk).exists())
        activo.refresh_from_db()
        self.assertEqual(activo.precio_unitario, Decimal('450'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_409_por_pago_en_curso_no_deja_extras_a_medias(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.post()

        extra = self.seleccionar_extra(precio=Decimal('300'), precio_usd=Decimal('18'))
        payment_intents.retrieve.return_value = intent_falso(status='processing')

        response = self.post()

        self.assertEqual(response.status_code, 409)
        extra.refresh_from_db()
        self.assertIsNone(extra.precio_unitario)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_cargo_en_dolares_no_se_cobra_a_medias(self, payment_intents):
        servicio = crear_servicio_pesca(self.empresa)
        servicio.precio_persona_extra_usd = None
        servicio.save(update_fields=['precio_persona_extra_usd'])
        reserva = crear_reserva(self.empresa, moneda='USD', numero_personas=5)
        response = self.client.post(
            reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
            {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_manda_idempotency_key(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.post()
        self.assertIn('idempotency_key', payment_intents.create.call_args.args[1])

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_dos_clics_reusan_el_mismo_intent(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.post()

        payment_intents.retrieve.return_value = intent_falso()
        response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment_intents.create.call_count, 1)  # no se creo un segundo intent

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cambiar_los_extras_ajusta_el_intent_en_vez_de_duplicarlo(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.post()

        # El cliente vuelve atras y agrega el brunch: mismo intent, otro monto.
        self.seleccionar_extra(precio=Decimal('150'), precio_usd=Decimal('9'))
        payment_intents.retrieve.return_value = intent_falso()
        payment_intents.update.return_value = intent_falso(amount=480000)
        self.post()

        self.assertEqual(payment_intents.create.call_count, 1)
        self.assertEqual(payment_intents.update.call_args.args[1]['amount'], a_centavos(Decimal('4800.00')))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_no_crea_otro_intent_si_ya_hay_uno_cobrando(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.post()

        payment_intents.retrieve.return_value = intent_falso(status='succeeded')
        response = self.post()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(payment_intents.create.call_count, 1)

    def test_reserva_ya_pagada_no_se_vuelve_a_cobrar(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save()
        self.assertEqual(self.post().status_code, 409)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_precio_en_dolares_responde_503(self, payment_intents):
        servicio = crear_servicio_pesca(self.empresa)
        servicio.precio_base_usd = None
        servicio.save(update_fields=['precio_base_usd'])
        reserva = crear_reserva(self.empresa, moneda='USD')
        response = self.client.post(
            reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
            {'amenities': [], 'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)
        payment_intents.create.assert_not_called()

    def test_forma_pago_invalida_responde_400(self):
        self.assertEqual(self.post(forma_pago='trueque').status_code, 400)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_el_checkout_id_correcto_no_se_puede_cobrar(self, payment_intents):
        """Los ids de reserva son consecutivos y la API es publica: adivinar uno
        no debe alcanzar para generar cobros sobre la reserva de otra persona."""
        self.assertEqual(self.post(checkout_id=None).status_code, 403)
        self.assertEqual(self.post(checkout_id='22222222-2222-4222-8222-222222222222').status_code, 403)
        payment_intents.create.assert_not_called()

        payment_intents.create.return_value = intent_falso()
        self.assertEqual(self.post(checkout_id=str(self.reserva.checkout_id)).status_code, 200)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_pago_con_servicio_estrategia_por_persona(self, payment_intents):
        from apps.fleet.models import Servicio
        payment_intents.create.return_value = intent_falso(amount=340000)
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo Espiritu Santo',
            slug='paseo-espiritu-santo',
            estrategia_precio='por_persona',
            precio_base=Decimal('850.00'),
        )
        self.reserva.servicio = servicio
        self.reserva.numero_personas = 4
        self.reserva.save(update_fields=['servicio', 'numero_personas'])

        response = self.post()
        self.assertEqual(response.status_code, 200)
        # 850 * 4 = 3400.00 -> 340000 centavos
        self.assertEqual(payment_intents.create.call_args[0][0]['amount'], 340000)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_pago_con_servicio_tarifa_fija(self, payment_intents):
        from apps.fleet.models import Servicio
        payment_intents.create.return_value = intent_falso(amount=1200000)
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Charter Exclusivo',
            slug='charter-exclusivo',
            estrategia_precio='tarifa_fija',
            precio_base=Decimal('12000.00'),
        )
        self.reserva.servicio = servicio
        self.reserva.numero_personas = 5
        self.reserva.save(update_fields=['servicio', 'numero_personas'])

        response = self.post()
        self.assertEqual(response.status_code, 200)
        # 12000.00 fijo -> 1200000 centavos
        self.assertEqual(payment_intents.create.call_args[0][0]['amount'], 1200000)

    def test_reserva_con_servicio_de_otra_empresa_falla_clean(self):
        from django.core.exceptions import ValidationError
        from apps.fleet.models import Servicio
        from apps.tenancy.models import Empresa
        empresa_otra = Empresa.objects.create(sede=self.empresa.sede, nombre='Otra', slug='otra-empresa')
        # con_empresa no es reentrante con otro valor: se cierra el alcance de
        # self.empresa (ApiTestCase) para sembrar en el de empresa_otra y se
        # reabre para el teardown.
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(empresa_otra):
                servicio_otro = Servicio.objects.create(
                    empresa=empresa_otra,
                    nombre='Tour Otro',
                    slug='tour-otro',
                    precio_base=Decimal('1000.00'),
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.reserva.servicio = servicio_otro
        with self.assertRaises(ValidationError):
            self.reserva.clean()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_una_reserva_de_whatsapp_no_se_cobra_por_esta_ruta(self, payment_intents):
        """Las que captura la vendedora no traen checkout_id, asi que no hay
        llave que las acredite: por aqui no se tocan.

        Con el guard escrito como `if reserva.checkout_id and ...` estas se
        colaban enteras — adivinando el id se sacaba su client_secret, se les
        pisaba el intent y se les podia cambiar la forma_pago a anticipo, que
        deja el viaje confirmado pagando el 30%."""
        self.reserva.checkout_id = None
        self.reserva.canal_origen = Reserva.CanalOrigen.WHATSAPP
        self.reserva.save()

        self.assertEqual(self.post(checkout_id=None).status_code, 403)
        # Tampoco vale mandar cualquier cosa, ni repetir el que tenia antes.
        self.assertEqual(self.post(checkout_id=CHECKOUT_ID).status_code, 403)
        payment_intents.create.assert_not_called()

    def test_el_403_no_delata_en_que_estado_esta_la_reserva(self):
        """El guard corre antes que la revision de estado, asi que quien no
        trae la llave recibe siempre lo mismo. Si se invirtiera el orden, el 409
        de 'ya no esta pendiente' le diria a un extraño cuales reservas ya se
        pagaron — recorriendo ids consecutivos, eso es un mapa del negocio."""
        ajeno = '22222222-2222-4222-8222-222222222222'
        self.assertEqual(self.post(checkout_id=ajeno).status_code, 403)

        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])

        self.assertEqual(self.post(checkout_id=ajeno).status_code, 403)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_codigo_promocional_valido_aplica_el_descuento(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )

        response = self.post(codigo_promocional='VERANO10')

        # 4500 - 10% = 4050.
        self.assertEqual(response.json()['monto_a_cobrar'], '4050.00')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.codigo_promocional.codigo, 'VERANO10')
        self.assertEqual(self.reserva.descuento_aplicado, Decimal('450.00'))
        self.assertEqual(self.reserva.precio_total, Decimal('4050.00'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_codigo_promocional_no_distingue_mayusculas_ni_espacios(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )

        response = self.post(codigo_promocional=' verano10 ')

        self.assertEqual(response.json()['monto_a_cobrar'], '4050.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_codigo_promocional_inexistente_responde_400(self, payment_intents):
        response = self.post(codigo_promocional='NOEXISTE')

        self.assertEqual(response.status_code, 400)
        payment_intents.create.assert_not_called()
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.codigo_promocional)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_codigo_promocional_inactivo_responde_400(self, payment_intents):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VIEJO', porcentaje_descuento=Decimal('10'), activo=False,
        )
        response = self.post(codigo_promocional='VIEJO')

        self.assertEqual(response.status_code, 400)
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_codigo_promocional_bajo_el_monto_minimo_responde_400(self, payment_intents):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='DESDE10000', porcentaje_descuento=Decimal('10'),
            monto_minimo=Decimal('10000'),
        )
        response = self.post(codigo_promocional='DESDE10000')

        self.assertEqual(response.status_code, 400)
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_codigo_promocional_no_hay_descuento(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.post()

        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.codigo_promocional)
        self.assertIsNone(self.reserva.descuento_aplicado)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_descuento_se_calcula_sobre_el_subtotal_con_extras(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )
        self.seleccionar_extra()  # 2 personas x 300 = 600

        # Subtotal: 4500 + 600 = 5100. Descuento 10% = 510. Total 4590.
        response = self.post(codigo_promocional='VERANO10')

        self.assertEqual(response.json()['monto_a_cobrar'], '4590.00')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.descuento_aplicado, Decimal('510.00'))


class ValidarCodigoPromocionalTests(ApiTestCase):
    def get(self, **params):
        return self.client.get(
            reverse('codigo-promocional-validar', kwargs={'empresa_slug': self.empresa.slug}),
            params,
        )

    def test_codigo_valido(self):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )
        body = self.get(codigo='VERANO10', correo_cliente='ana@example.com').json()
        self.assertEqual(body, {'valido': True, 'porcentaje_descuento': '10.00'})

    def test_codigo_no_distingue_mayusculas_ni_espacios(self):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )
        body = self.get(codigo=' verano10 ', correo_cliente='ana@example.com').json()
        self.assertTrue(body['valido'])

    def test_codigo_inexistente(self):
        body = self.get(codigo='NOEXISTE', correo_cliente='ana@example.com').json()
        self.assertEqual(body, {'valido': False, 'porcentaje_descuento': None})

    def test_codigo_inactivo_da_la_misma_respuesta_generica_que_uno_inexistente(self):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VIEJO', porcentaje_descuento=Decimal('10'), activo=False,
        )
        self.assertEqual(
            self.get(codigo='VIEJO', correo_cliente='ana@example.com').json(),
            self.get(codigo='NOEXISTE', correo_cliente='ana@example.com').json(),
        )

    def test_sin_codigo_no_es_valido(self):
        body = self.get(codigo='', correo_cliente='ana@example.com').json()
        self.assertEqual(body, {'valido': False, 'porcentaje_descuento': None})

    def test_agotado_para_este_cliente_no_es_valido(self):
        promo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='UNAVEZ', porcentaje_descuento=Decimal('10'),
            usos_maximos_por_cliente=1,
        )
        crear_reserva(
            self.empresa,
            codigo_promocional=promo, estado=Reserva.Estado.PAGADA,
            correo_cliente='repetido@example.com',
        )
        body = self.get(codigo='UNAVEZ', correo_cliente='repetido@example.com').json()
        self.assertFalse(body['valido'])


class EstadoReservaTests(ApiTestCase):
    """El endpoint de recuperacion del checkout (`/api/reservas/estado/`).

    Nace de un caso real: recargar o cerrar por accidente a media compra
    dejaba el checkout en blanco. Si el pago ya habia pasado, el cliente se
    topaba con el 409 de `crear-pago` sin ninguna forma de ver su confirmacion
    — un cliente que ya pago viendo una pantalla de error. Esto expone lo que
    hace falta para reponer esa pantalla, sin volver a golpear a Stripe."""

    def setUp(self):
        self.reserva = crear_reserva(self.empresa)

    def get(self, checkout_id):
        return self.client.get(
            reverse('reserva-estado', kwargs={'empresa_slug': self.empresa.slug}),
            {'checkout_id': checkout_id},
        )

    def test_checkout_id_invalido_responde_400(self):
        self.assertEqual(self.get('no-es-un-uuid').status_code, 400)

    def test_checkout_id_sin_reserva_responde_404(self):
        ajeno = '22222222-2222-4222-8222-222222222222'
        self.assertEqual(self.get(ajeno).status_code, 404)

    def test_pendiente_de_pago_repone_lo_necesario_para_el_formulario(self):
        response = self.get(str(self.reserva.checkout_id))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['estado'], 'pendiente_pago')
        self.assertEqual(body['reserva_id'], self.reserva.pk)
        self.assertEqual(body['nombre_cliente'], 'Ana Ruiz')
        self.assertEqual(body['telefono_cliente'], '+5216121234567')
        self.assertEqual(body['correo_cliente'], 'ana@example.com')
        # Nada de Stripe ni de la constancia legal del deslinde: esta ruta no
        # llama a Stripe y el deslinde no se repone solo.
        self.assertNotIn('stripe_payment_intent_id', body)
        self.assertNotIn('deslinde_aceptado', body)

    def test_pendiente_de_pago_repone_la_cantidad_elegida_de_extras(self):
        """Sin esto, recargar la pagina a medio checkout perderia la cantidad
        que el cliente ya habia elegido para un extra con `cantidad_editable`
        (ver fleet.Personalizacion.cantidad_editable)."""
        licencia = crear_personalizacion_pesca(
            empresa=self.empresa,
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            cantidad_editable=True,
        )
        ReservaPersonalizacion.objects.create(
            reserva=self.reserva, servicio_personalizacion=licencia, cantidad=2,
        )

        body = self.get(str(self.reserva.checkout_id)).json()

        self.assertEqual(body['personalizaciones'], [{'id': licencia.pk, 'cantidad': 2, 'respuesta': ''}])

    def test_pagada_repone_lo_necesario_para_la_confirmacion_sin_telefono(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.monto_pagado = Decimal('4500.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.save()

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertEqual(body['estado'], 'pagada')
        self.assertEqual(body['monto_pagado'], '4500.00')
        # La confirmacion no muestra telefono: no se manda de vuelta.
        self.assertNotIn('telefono_cliente', body)

    def test_pagada_incluye_el_desglose_de_extras_ya_congelado(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.precio_total = Decimal('5400.00')
        self.reserva.monto_pagado = Decimal('5400.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.save()

        item = crear_personalizacion_pesca(
            empresa=self.empresa,
            tipo='brunch', nombre='Brunch', precio=Decimal('300'),
            cobrar_por_persona=True,
        )
        ReservaPersonalizacion.objects.create(
            reserva=self.reserva, servicio_personalizacion=item,
            precio_unitario=Decimal('300'), cantidad=self.reserva.numero_personas,
        )

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertEqual(body['personalizaciones'], [
            {
                'nombre': 'Brunch', 'tipo_interaccion': 'check', 'respuesta': '', 'monto': '600.00',
                'cantidad': self.reserva.numero_personas,
            },
        ])

    def test_pagada_sin_extras_los_manda_vacios(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertEqual(body['personalizaciones'], [])

    def test_pagada_incluye_el_codigo_promocional_y_descuento_ya_congelados(self):
        promo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.precio_total = Decimal('4050.00')
        self.reserva.monto_pagado = Decimal('4050.00')
        self.reserva.codigo_promocional = promo
        self.reserva.descuento_aplicado = Decimal('450.00')
        self.reserva.save()

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertEqual(body['codigo_promocional'], 'VERANO10')
        self.assertEqual(body['descuento_aplicado'], '450.00')

    def test_pagada_sin_codigo_promocional_manda_ambos_en_none(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertIsNone(body['codigo_promocional'])
        self.assertIsNone(body['descuento_aplicado'])

    def test_asignada_y_completada_cuentan_como_pagada(self):
        for estado in (Reserva.Estado.ASIGNADA, Reserva.Estado.COMPLETADA):
            self.reserva.estado = estado
            self.reserva.save(update_fields=['estado'])
            self.assertEqual(self.get(str(self.reserva.checkout_id)).json()['estado'], 'pagada')

    def test_cancelada_no_manda_ningun_dato_personal(self):
        self.reserva.estado = Reserva.Estado.CANCELADA
        self.reserva.save(update_fields=['estado'])

        self.assertEqual(self.get(str(self.reserva.checkout_id)).json(), {'estado': 'cancelada'})

    def test_dos_reservas_con_el_mismo_checkout_id_devuelve_la_mas_reciente(self):
        """checkout_id no es unico a proposito (la misma pestana puede reservar
        dos viajes seguidos): quien pregunta por el debe ver la sesion que esta
        corriendo ahora, no la primera que encuentre la base."""
        vieja = self.reserva
        vieja.estado = Reserva.Estado.PAGADA
        vieja.save(update_fields=['estado'])

        nueva = crear_reserva(
            self.empresa,
            fecha=date.today() + timedelta(days=20), nombre_cliente='Otro Cliente',
        )
        self.assertEqual(nueva.checkout_id, vieja.checkout_id)
        body = self.get(str(vieja.checkout_id)).json()
        self.assertEqual(body['estado'], 'pendiente_pago')
        self.assertEqual(body['reserva_id'], nueva.pk)

    def test_un_checkout_id_ajeno_no_revela_nada(self):
        """Mismo principio que ya protege a `crear-pago`: el UUID es la unica
        llave, y sin acertarlo no hay estado ni dato que ver."""
        ajeno = '33333333-3333-4333-8333-333333333333'
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])

        self.assertEqual(self.get(ajeno).status_code, 404)


@override_settings(**LLAVES)
class WebhookTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])
        crear_servicio_pesca(
            self.empresa, precio_base=Decimal('4500.00'), precio_base_usd=None,
            precio_persona_extra=Decimal('0'), precio_persona_extra_usd=None,
        )
        self.reserva = crear_reserva(self.empresa)
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.stripe_payment_intent_id = 'pi_1'
        self.reserva.save()

    def entregar(self, evento):
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json',
                HTTP_STRIPE_SIGNATURE='falsa',
            )

    def test_marca_pagada_y_guarda_lo_cobrado(self):
        self.assertEqual(self.entregar(evento_pagado(self.reserva.pk)).status_code, 200)

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        self.assertEqual(self.reserva.saldo_pendiente, Decimal('0.00'))
        self.assertIsNotNone(self.reserva.pagada_en)

    def test_el_dinero_se_fecha_con_el_reloj_de_stripe(self):
        """`conciliar_pagos` puede aplicar dias despues un pago cuyo webhook se
        perdio. Ese dinero cuenta en el dia en que entro, no en el dia en que el
        sistema se entero, o el balance de ese dia nunca cuadra."""
        evento = evento_pagado(self.reserva.pk)
        evento['data']['object']['created'] = 1772000000

        self.entregar(evento)

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.pagada_en, datetime.fromtimestamp(1772000000, UTC))

    @mock.patch.object(StripeClient, 'refunds')
    def test_el_mismo_evento_dos_veces_no_cobra_ni_reembolsa_de_mas(self, refunds):
        self.entregar(evento_pagado(self.reserva.pk))
        self.entregar(evento_pagado(self.reserva.pk))

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        refunds.create.assert_not_called()

    @mock.patch.object(StripeClient, 'refunds')
    def test_un_segundo_cobro_distinto_se_reembolsa(self, refunds):
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_1'))
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_2'))

        refunds.create.assert_called_once()
        self.assertEqual(refunds.create.call_args.args[0]['payment_intent'], 'pi_2')
        # La reserva conserva el primer cobro, no se duplica el monto.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        self.assertEqual(self.reserva.stripe_payment_intent_id, 'pi_1')

    @mock.patch.object(StripeClient, 'refunds')
    def test_pago_sin_reserva_se_reembolsa(self, refunds):
        self.assertEqual(self.entregar(evento_pagado(99999)).status_code, 200)
        refunds.create.assert_called_once()

    @mock.patch.object(StripeClient, 'refunds')
    def test_si_el_dia_se_lleno_reembolsa_y_cancela(self, refunds):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(self.empresa, fecha=self.reserva.fecha, estado=Reserva.Estado.PAGADA)

        self.entregar(evento_pagado(self.reserva.pk))

        refunds.create.assert_called_once()
        # El cobro y su devolucion quedan los dos registrados: en la cuenta de
        # verdad entro y salio ese dinero, y el panel de finanzas tiene que
        # poder contarlo asi.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        self.assertEqual(self.reserva.monto_reembolsado, Decimal('4500.00'))
        self.assertIsNotNone(self.reserva.reembolsada_en)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(self.reserva.reembolsada)
        self.assertIn('Sin cupo', self.reserva.motivo_cancelacion)

    @mock.patch.object(StripeClient, 'refunds')
    def test_si_el_codigo_promocional_ya_no_es_valido_reembolsa_y_cancela(self, refunds):
        """El codigo se agoto (otra reserva se adelanto) entre `crear-pago` y el
        webhook: mismo remedio que el cupo lleno, con el motivo real."""
        promo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'), usos_maximos=1,
        )
        self.reserva.codigo_promocional = promo
        self.reserva.descuento_aplicado = Decimal('450.00')
        self.reserva.precio_total = Decimal('4050.00')
        self.reserva.save()
        crear_reserva(
            self.empresa,
            fecha=self.reserva.fecha, codigo_promocional=promo, estado=Reserva.Estado.PAGADA,
        )

        self.entregar(evento_pagado(self.reserva.pk, amount=405000))

        refunds.create.assert_called_once()
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(self.reserva.reembolsada)
        self.assertEqual(self.reserva.monto_reembolsado, Decimal('4050.00'))
        self.assertIn('codigo promocional', self.reserva.motivo_cancelacion)

    @mock.patch.object(StripeClient, 'refunds')
    def test_si_falla_el_reembolso_no_se_cancela_a_ciegas(self, refunds):
        refunds.create.side_effect = stripe.APIConnectionError('stripe caido')
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(self.empresa, fecha=self.reserva.fecha, estado=Reserva.Estado.PAGADA)

        self.assertEqual(self.entregar(evento_pagado(self.reserva.pk)).status_code, 200)

        # Sigue pendiente_pago: no se marca reembolsada una reserva cuyo dinero
        # nunca se devolvio.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertFalse(self.reserva.reembolsada)

    @mock.patch.object(StripeClient, 'refunds')
    def test_el_reembolso_manda_idempotency_key_en_options_no_en_params(self, refunds):
        """Regresión directa de la Revisión 6, N-D: `idempotency_key` en `params`
        en vez de `options` pierde la protección de doble reembolso — Stripe la
        ignoraría como un campo más del payload, no como la cabecera
        `Idempotency-Key`."""
        self.entregar(evento_pagado(99999))  # pago sin reserva -> se reembolsa

        refunds.create.assert_called_once()
        params, options = refunds.create.call_args.args
        self.assertNotIn('idempotency_key', params)
        self.assertIn('idempotency_key', options)

    def test_registra_el_descuadre_pero_no_rebota_el_pago(self):
        with self.assertLogs('apps.payments.services', level='ERROR') as logs:
            self.entregar(evento_pagado(self.reserva.pk, amount=100000))

        self.assertIn('Descuadre', '\n'.join(logs.output))
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(self.reserva.monto_pagado, Decimal('1000.00'))
        self.assertEqual(self.reserva.saldo_pendiente, Decimal('3500.00'))

    def test_webhook_paquete_pago_completo_no_registra_descuadre(self):
        paquete = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Total',
            slug='paquete-total',
            precio_ancla=Decimal('8000.00'),
            permite_anticipo=False,
        )
        reserva = crear_reserva(self.empresa, paquete=paquete, servicio=None)
        reserva.precio_total = Decimal('8000.00')
        reserva.forma_pago = Reserva.FormaPago.COMPLETO
        reserva.stripe_payment_intent_id = 'pi_paquete_completo'
        reserva.save()

        with self.assertNoLogs('apps.payments.services', level='ERROR'):
            resp = self.entregar(evento_pagado(reserva.pk, amount=800000, intent_id='pi_paquete_completo'))
        self.assertEqual(resp.status_code, 200)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.monto_pagado, Decimal('8000.00'))

    def test_firma_invalida_responde_400(self):
        with mock.patch('stripe.Webhook.construct_event', side_effect=ValueError):
            response = self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json',
                HTTP_STRIPE_SIGNATURE='falsa',
            )
        self.assertEqual(response.status_code, 400)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    def test_otros_eventos_se_ignoran(self):
        evento = {'id': 'evt_2', 'type': 'payment_intent.created', 'data': {'object': {}}}
        self.assertEqual(self.entregar(evento).status_code, 200)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)


@override_settings(**LLAVES)
class EventosDeStripeTests(ApiTestCase):
    """Reembolsos y contracargos. Sin escuchar estos eventos, el dinero se mueve
    en Stripe y la base sigue contando otra historia."""

    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])
        crear_servicio_pesca(
            self.empresa, precio_base=Decimal('4500.00'), precio_base_usd=None,
            precio_persona_extra=Decimal('0'), precio_persona_extra_usd=None,
        )
        self.reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.monto_pagado = Decimal('4500.00')
        self.reserva.stripe_payment_intent_id = 'pi_1'
        self.reserva.save()

    def entregar(self, tipo, objeto):
        evento = {'id': 'evt_x', 'type': tipo, 'data': {'object': objeto}}
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json',
                HTTP_STRIPE_SIGNATURE='falsa',
            )

    def test_un_reembolso_hecho_en_stripe_se_refleja(self):
        self.assertFalse(self.reserva.reembolsada)

        self.entregar('charge.refunded', {'id': 'ch_1', 'payment_intent': 'pi_1'})

        self.reserva.refresh_from_db()
        self.assertTrue(self.reserva.reembolsada)

    def test_el_reembolso_registra_cuanto_salio_y_cuando(self):
        """Sin monto ni fecha, el panel de finanzas no puede restar la salida."""
        self.entregar('charge.refunded', {
            'id': 'ch_1', 'payment_intent': 'pi_1', 'amount_refunded': 450000,
        })

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_reembolsado, Decimal('4500.00'))
        self.assertIsNotNone(self.reserva.reembolsada_en)

    def test_reprocesar_el_evento_no_infla_la_salida(self):
        objeto = {'id': 'ch_1', 'payment_intent': 'pi_1', 'amount_refunded': 450000}
        self.entregar('charge.refunded', objeto)
        self.reserva.refresh_from_db()
        primera_fecha = self.reserva.reembolsada_en

        self.entregar('charge.refunded', objeto)

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_reembolsado, Decimal('4500.00'))
        self.assertEqual(self.reserva.reembolsada_en, primera_fecha)

    def test_una_disputa_levanta_la_bandera(self):
        self.entregar('charge.dispute.created', {'id': 'dp_1', 'payment_intent': 'pi_1'})

        self.reserva.refresh_from_db()
        self.assertTrue(self.reserva.en_disputa)

    def test_al_cerrarse_la_disputa_se_baja(self):
        self.entregar('charge.dispute.created', {'id': 'dp_1', 'payment_intent': 'pi_1'})
        self.entregar('charge.dispute.closed', {'id': 'dp_1', 'payment_intent': 'pi_1'})

        self.reserva.refresh_from_db()
        self.assertFalse(self.reserva.en_disputa)

    def test_la_disputa_no_cambia_el_estado_de_la_reserva(self):
        # Que hacer con un viaje en disputa lo decide una persona, no el sistema.
        self.entregar('charge.dispute.created', {'id': 'dp_1', 'payment_intent': 'pi_1'})

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)

    def test_un_cargo_ajeno_no_toca_nada(self):
        respuesta = self.entregar('charge.refunded', {'id': 'ch_9', 'payment_intent': 'pi_otro'})

        self.assertEqual(respuesta.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertFalse(self.reserva.reembolsada)


@override_settings(**LLAVES)
class ConciliarPagosTests(EmpresaTestCase):
    """El webhook puede perderse para siempre. Sin esta red, el cliente pago y
    no tiene reserva, y nadie se entera hasta que reclama."""

    def setUp(self):
        # Asegurar que la empresa de prueba tiene llaves para que conciliar_pagos
        # no la salte (itera Empresa.objects.all(), requiere stripe_secret_key).
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])
        crear_servicio_pesca(
            self.empresa, precio_base=Decimal('4500.00'), precio_base_usd=None,
            precio_persona_extra=Decimal('0'), precio_persona_extra_usd=None,
        )
        self.reserva = crear_reserva(self.empresa)
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.stripe_payment_intent_id = 'pi_1'
        self.reserva.save()

    def ejecutar(self, **kwargs):
        salida = StringIO()
        call_command('conciliar_pagos', stdout=salida, stderr=StringIO(), **kwargs)
        return salida.getvalue()

    def intent_stripe(self, status='succeeded', amount=450000):
        """PaymentIntent real de la libreria, no un Mock: el `metadata` de un
        StripeObject no se comporta como un dict y ahi se escondia un bug."""
        return stripe.PaymentIntent.construct_from(
            {
                'id': 'pi_1',
                'status': status,
                'amount_received': amount,
                'currency': 'mxn',
                'metadata': {'reserva_id': str(self.reserva.pk)},
            },
            'sk_test_falsa',
        )

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_aplica_el_pago_que_el_webhook_nunca_entrego(self, payment_intents):
        payment_intents.retrieve.return_value = self.intent_stripe()
        self.ejecutar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_dry_run_no_toca_nada(self, payment_intents):
        payment_intents.retrieve.return_value = self.intent_stripe()
        salida = self.ejecutar(dry_run=True)

        self.assertIn('succeeded', salida)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_no_toca_los_que_no_se_pagaron(self, payment_intents):
        payment_intents.retrieve.return_value = self.intent_stripe(status='requires_payment_method')
        self.ejecutar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_ignora_las_reservas_sin_intent(self, payment_intents):
        Reserva.objects.filter(pk=self.reserva.pk).update(stripe_payment_intent_id='')
        self.ejecutar()
        payment_intents.retrieve.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_correr_dos_veces_no_duplica_nada(self, payment_intents):
        payment_intents.retrieve.return_value = self.intent_stripe()
        self.ejecutar()
        self.ejecutar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        # La segunda vuelta ya no la ve: dejo de estar pendiente.
        self.assertEqual(payment_intents.retrieve.call_count, 1)


class VersionDeApiTests(TestCase):
    """La version de la API de Stripe se fija de forma explicita.

    La libreria ya manda una por su cuenta, asi que esto no cambia el
    comportamiento — cambia de donde sale el numero. Sin fijarla, la version de
    la API viaja pegada a la de la libreria y un `pip install -U stripe` la
    moveria en silencio, sin que aparezca en ningun diff que Stripe empezo a
    contestar con otro formato.
    """

    def test_la_version_fijada_es_la_que_espera_la_libreria_instalada(self):
        """Si al subir `stripe` en requirements.txt no se revisa este valor, la
        libreria y la version de API dejarian de coincidir. Este test obliga a
        tomar la decision a proposito en vez de arrastrarla."""
        from django.conf import settings as cfg

        self.assertEqual(
            cfg.STRIPE_API_VERSION, stripe.api_version,
            'STRIPE_API_VERSION no coincide con la que trae stripe=='
            f'{stripe.VERSION}. Al actualizar la libreria hay que leer el '
            'changelog de Stripe y decidir si se sube tambien la version de API.',
        )


class ConfigurarStripeTests(TestCase):
    """configurar_stripe(empresa) devuelve un cliente explicito, sin tocar
    stripe.api_key/api_version como estado global del proceso."""

    def setUp(self):
        # Slugs deliberadamente distintos de 'la-paz'/'sal-y-sol' -- esas filas
        # ya existen, sembradas por tenancy.0002_crear_sede_empresa_la_paz (ver
        # apps/testing.py, misma razon con SLUG_EMPRESA_DE_PRUEBA).
        sede = Sede.objects.create(
            nombre='Sede stripe test', slug='sede-stripe-test', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=sede, nombre='Empresa stripe test', slug='empresa-stripe-test',
            stripe_secret_key='sk_test_abc', stripe_webhook_secret='whsec_abc',
            stripe_publishable_key='pk_test_abc',
        )

    @mock.patch('apps.payments.stripe_client.stripe.StripeClient')
    def test_usa_las_llaves_de_la_empresa(self, mock_cliente_cls):
        from django.conf import settings as django_settings

        resultado = configurar_stripe(self.empresa)

        mock_cliente_cls.assert_called_once_with(
            api_key='sk_test_abc', stripe_version=django_settings.STRIPE_API_VERSION,
        )
        self.assertIs(resultado, mock_cliente_cls.return_value)

    def test_no_muta_stripe_api_key_global(self):
        api_key_antes = getattr(stripe, 'api_key', None)
        configurar_stripe(self.empresa)
        self.assertEqual(getattr(stripe, 'api_key', None), api_key_antes)


class NotificarReservaPagadaOnCommitTests(TransactionTestCase):
    """TransactionTestCase, no TestCase: transaction.on_commit solo dispara
    con un commit real — TestCase envuelve cada test en una transaccion que
    nunca comitea, y el callback nunca correria.

    Prueba directa del bug N1 (Revision 4): SET LOCAL muere al COMMIT, asi que
    el callback de on_commit debe reabrir su propio con_empresa — si no lo
    hace, este test lo detecta viendo connection.alcance_actual en None (o en
    la Empresa equivocada) dentro del callback.
    """

    def setUp(self):
        # Slugs distintos de 'la-paz'/'sal-y-sol' -- ya existen, sembrados por
        # tenancy.0002_crear_sede_empresa_la_paz.
        self.sede = Sede.objects.create(
            nombre='Sede on-commit test', slug='sede-on-commit-test', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa on-commit test', slug='empresa-on-commit-test',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_x',
        )
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)

    def _crear_reserva(self):
        reserva = Reserva(
            empresa=self.empresa, servicio=crear_servicio_pesca(self.empresa),
            fecha=date.today() + timedelta(days=10),
            hora=time(6, 0), numero_personas=2, nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz', checkout_id=uuid.uuid4(), moneda='MXN',
        )
        with scope.con_empresa(self.empresa):
            reserva.full_clean()
            reserva.save()
        return reserva

    @mock.patch('apps.payments.services.notificar_reserva_pagada')
    def test_el_callback_ve_el_alcance_correcto_tras_el_commit(self, mock_notificar):
        reserva = self._crear_reserva()
        intent = {
            'id': 'pi_1', 'amount_received': 157500, 'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }

        capturado = {}

        def _espia(reserva_arg):
            capturado['alcance'] = connection.alcance_actual
            capturado['reserva_id'] = reserva_arg.pk

        mock_notificar.side_effect = _espia

        with scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)

        self.assertEqual(resultado, APLICADO)
        mock_notificar.assert_called_once()
        # alcance_actual es ('empresa', id), no el id solo (ver apps.tenancy.scope).
        self.assertEqual(capturado['alcance'], ('empresa', self.empresa.pk))
        self.assertEqual(capturado['reserva_id'], reserva.pk)


class ReembolsarTests(TestCase):
    def setUp(self):
        sede = Sede.objects.create(
            nombre='Sede reembolsar test', slug='sede-reembolsar-test', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=sede, nombre='Empresa reembolsar test', slug='empresa-reembolsar-test',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_x',
        )

    @mock.patch('apps.payments.services.configurar_stripe')
    def test_idempotency_key_va_en_options_no_en_params(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente

        resultado = reembolsar({'id': 'pi_1'}, 'prueba', self.empresa)

        self.assertTrue(resultado)
        mock_configurar.assert_called_once_with(self.empresa)
        params, options = cliente.refunds.create.call_args.args
        self.assertEqual(params, {'payment_intent': 'pi_1'})
        self.assertNotIn('idempotency_key', params)
        self.assertEqual(options, {'idempotency_key': 'refund-pi_1'})

    @mock.patch('apps.payments.services.configurar_stripe')
    def test_stripe_error_devuelve_false(self, mock_configurar):
        cliente = mock.Mock()
        cliente.refunds.create.side_effect = stripe.StripeError('boom')
        mock_configurar.return_value = cliente
        self.assertFalse(reembolsar({'id': 'pi_1'}, 'prueba', self.empresa))


class ReservaDelCargoAisladaPorEmpresaTests(TestCase):
    def setUp(self):
        sede = Sede.objects.create(
            nombre='Sede cargo test', slug='sede-cargo-test', zona_horaria='America/Mazatlan',
        )
        self.empresa_a = Empresa.objects.create(
            sede=sede, nombre='A', slug='empresa-cargo-a',
            stripe_secret_key='sk_a', stripe_webhook_secret='whsec_a',
            stripe_publishable_key='pk_a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=sede, nombre='B', slug='empresa-cargo-b',
            stripe_secret_key='sk_b', stripe_webhook_secret='whsec_b',
            stripe_publishable_key='pk_b',
        )
        with scope.con_empresa(self.empresa_a):
            crear_flota(self.empresa_a)
            self.reserva_a = Reserva(
                empresa=self.empresa_a, servicio=crear_servicio_pesca(self.empresa_a),
                fecha=date.today() + timedelta(days=10),
                hora=time(6, 0), numero_personas=2, nombre_cliente='Ana',
                telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
                canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
                deslinde_nombre='Ana', checkout_id=uuid.uuid4(), moneda='MXN',
                stripe_payment_intent_id='pi_compartido',
            )
            self.reserva_a.full_clean()
            self.reserva_a.save()

    def test_no_encuentra_la_reserva_de_otra_empresa(self):
        with scope.con_empresa(self.empresa_b):
            self.assertIsNone(
                _reserva_del_cargo({'payment_intent': 'pi_compartido'}, self.empresa_b)
            )

    def test_encuentra_la_reserva_de_su_propia_empresa(self):
        with scope.con_empresa(self.empresa_a):
            encontrada = _reserva_del_cargo({'payment_intent': 'pi_compartido'}, self.empresa_a)
        self.assertEqual(encontrada.pk, self.reserva_a.pk)


class IntentDeTests(TestCase):
    """_intent_de habla con el StripeClient explicito (P1), no con el modulo
    stripe global, y usa la forma real del SDK: update (no modify),
    idempotency_key en options (no en params)."""

    def setUp(self):
        self.view = CrearPagoView()
        self.reserva = mock.Mock(stripe_payment_intent_id='', pk=42, moneda='MXN')

    def test_crea_intent_nuevo_con_idempotency_en_options(self):
        cliente = mock.Mock()
        cliente.payment_intents.create.return_value = mock.Mock(id='pi_new')

        self.view._intent_de(cliente, self.reserva, Decimal('100.00'))

        params, options = cliente.payment_intents.create.call_args.args
        self.assertNotIn('idempotency_key', params)
        self.assertEqual(params['amount'], 10000)
        self.assertEqual(params['currency'], 'mxn')
        self.assertEqual(options, {'idempotency_key': 'reserva-42-mxn-10000'})

    def test_reutiliza_intent_reutilizable_mismo_monto(self):
        self.reserva.stripe_payment_intent_id = 'pi_1'
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(
            status='requires_payment_method', amount=10000, currency='mxn', id='pi_1',
        )

        resultado = self.view._intent_de(cliente, self.reserva, Decimal('100.00'))

        cliente.payment_intents.update.assert_not_called()
        self.assertEqual(resultado.id, 'pi_1')

    def test_ajusta_intent_con_update_no_modify(self):
        self.reserva.stripe_payment_intent_id = 'pi_1'
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(
            status='requires_payment_method', amount=5000, currency='mxn', id='pi_1',
        )

        self.view._intent_de(cliente, self.reserva, Decimal('100.00'))

        cliente.payment_intents.update.assert_called_once_with(
            'pi_1', {'amount': 10000, 'currency': 'mxn'},
        )

    def test_intent_ya_cobrando_lanza_pago_en_curso(self):
        self.reserva.stripe_payment_intent_id = 'pi_1'
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(status='succeeded')

        with self.assertRaises(PagoEnCurso):
            self.view._intent_de(cliente, self.reserva, Decimal('100.00'))


class ResolverCodigoPromocionalMultipleTests(TestCase):
    """N6: dos Empresas con el mismo codigo (posible tras quitar unique=True
    global) no debe reventar el checkout con 500."""

    def setUp(self):
        self.view = CrearPagoView()
        self.sede = Sede.objects.create(
            nombre='Sede codigo test', slug='sede-codigo-test', zona_horaria='America/Mazatlan',
        )
        self.empresa_a = Empresa.objects.create(
            sede=self.sede, nombre='A', slug='empresa-codigo-a',
            stripe_secret_key='sk_a', stripe_webhook_secret='whsec_a',
            stripe_publishable_key='pk_a',
        )

    @mock.patch('apps.payments.views.CodigoPromocional.objects')
    def test_multiple_objects_returned_da_400_no_500(self, mock_objects):
        mock_objects.get.side_effect = CodigoPromocional.MultipleObjectsReturned
        reserva = mock.Mock(correo_cliente='cliente@example.com', moneda='MXN')

        _, descuento, error = self.view._resolver_codigo_promocional(
            mock.Mock(data={'codigo_promocional': 'VERANO10'}),
            reserva, Decimal('1000.00'), self.empresa_a,
        )

        self.assertEqual(descuento, 0)
        self.assertEqual(error, 'El codigo promocional no es valido.')


class StripeWebhookViewUsaLaEmpresaDelSlugTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch('apps.payments.views.aplicar_pago_exitoso')
    @mock.patch('apps.payments.views.scope.con_empresa')
    @mock.patch('apps.payments.views.scope.resolver_empresa_de_dinero')
    @mock.patch('apps.payments.views.stripe.Webhook.construct_event')
    def test_usa_el_webhook_secret_de_la_empresa_aunque_este_pausada(
        self, mock_construct, mock_resolver, mock_con_empresa, mock_aplicar,
    ):
        empresa = mock.Mock(stripe_webhook_secret='whsec_empresa_x', activo=False)
        mock_resolver.return_value = empresa
        mock_con_empresa.return_value.__enter__ = mock.Mock()
        mock_con_empresa.return_value.__exit__ = mock.Mock(return_value=False)
        mock_construct.return_value = {
            'id': 'evt_1', 'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_1'}},
        }

        request = self.factory.post(
            '/api/sal-y-sol/stripe/webhook/', data=b'{}',
            content_type='application/json', HTTP_STRIPE_SIGNATURE='firma',
        )
        response = StripeWebhookView.as_view()(request, empresa_slug='sal-y-sol')

        mock_resolver.assert_called_once_with('sal-y-sol')
        self.assertEqual(mock_construct.call_args.args[2], 'whsec_empresa_x')
        mock_aplicar.assert_called_once_with({'id': 'pi_1'}, empresa)
        self.assertEqual(response.status_code, 200)


class EstadoReservaViewFiltraPorEmpresaTests(TestCase):
    @mock.patch('apps.payments.views.scope.con_empresa')
    @mock.patch('apps.payments.views.scope.resolver_empresa_publica')
    @mock.patch('apps.payments.views.Reserva.objects.filter')
    def test_filtra_la_reserva_por_empresa(self, mock_filter, mock_resolver, mock_con_empresa):
        empresa = mock.Mock()
        mock_resolver.return_value = empresa
        mock_con_empresa.return_value.__enter__ = mock.Mock()
        mock_con_empresa.return_value.__exit__ = mock.Mock(return_value=False)
        mock_filter.return_value.order_by.return_value.first.return_value = None

        request = RequestFactory().get(
            '/api/sal-y-sol/reservas/estado/',
            {'checkout_id': '11111111-1111-4111-8111-111111111111'},
        )
        EstadoReservaView.as_view()(request, empresa_slug='sal-y-sol')

        mock_filter.assert_called_once_with(
            checkout_id=uuid.UUID('11111111-1111-4111-8111-111111111111'), empresa=empresa,
        )


class ValidarCodigoPromocionalViewPasaLaEmpresaTests(TestCase):
    @mock.patch('apps.payments.views.evaluar_codigo_promocional')
    @mock.patch('apps.payments.views.scope.con_empresa')
    @mock.patch('apps.payments.views.scope.resolver_empresa_publica')
    def test_pasa_la_empresa_resuelta(self, mock_resolver, mock_con_empresa, mock_evaluar):
        empresa = mock.Mock()
        mock_resolver.return_value = empresa
        mock_con_empresa.return_value.__enter__ = mock.Mock()
        mock_con_empresa.return_value.__exit__ = mock.Mock(return_value=False)
        mock_evaluar.return_value = None

        request = RequestFactory().get(
            '/api/sal-y-sol/codigo-promocional/validar/',
            {'codigo': 'VERANO10', 'correo_cliente': 'a@example.com'},
        )
        ValidarCodigoPromocionalView.as_view()(request, empresa_slug='sal-y-sol')

        mock_evaluar.assert_called_once_with('VERANO10', 'a@example.com', empresa)


class PaymentsUrlsTests(TestCase):
    def test_crear_pago_incluye_el_slug(self):
        url = reverse('crear-pago', kwargs={'empresa_slug': 'sal-y-sol', 'pk': 1})
        self.assertEqual(url, '/api/sal-y-sol/reservas/1/crear-pago/')

    def test_reserva_estado_incluye_el_slug(self):
        url = reverse('reserva-estado', kwargs={'empresa_slug': 'sal-y-sol'})
        self.assertEqual(url, '/api/sal-y-sol/reservas/estado/')

    def test_codigo_promocional_validar_incluye_el_slug(self):
        url = reverse('codigo-promocional-validar', kwargs={'empresa_slug': 'sal-y-sol'})
        self.assertEqual(url, '/api/sal-y-sol/codigo-promocional/validar/')

    def test_stripe_webhook_incluye_el_slug(self):
        url = reverse('stripe-webhook', kwargs={'empresa_slug': 'sal-y-sol'})
        self.assertEqual(url, '/api/sal-y-sol/stripe/webhook/')


class ConciliarPagosPorEmpresaTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='Sede conciliar test', slug='sede-conciliar-test', zona_horaria='America/Mazatlan',
        )
        self.empresa_con_llave = Empresa.objects.create(
            sede=self.sede, nombre='Con llave', slug='con-llave',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_x',
        )
        self.empresa_sin_llave = Empresa.objects.create(
            sede=self.sede, nombre='Sin llave', slug='sin-llave',
            stripe_secret_key='', stripe_webhook_secret='', stripe_publishable_key='',
        )

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_se_salta_empresas_sin_llave_sin_abortar_el_comando(self, mock_configurar):
        salida = StringIO()
        call_command('conciliar_pagos', '--dry-run', stdout=salida)

        mock_configurar.assert_called_once_with(self.empresa_con_llave)
        texto = salida.getvalue()
        self.assertIn('sin-llave', texto)
        self.assertIn('sin llave de Stripe', texto)

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_itera_tambien_empresas_pausadas(self, mock_configurar):
        self.empresa_con_llave.activo = False
        self.empresa_con_llave.save(update_fields=['activo'])

        call_command('conciliar_pagos', '--dry-run', stdout=StringIO())

        mock_configurar.assert_called_once_with(self.empresa_con_llave)

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_filtra_las_reservas_pendientes_por_empresa(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente
        with scope.con_empresa(self.empresa_con_llave):
            crear_flota(self.empresa_con_llave)
            reserva = Reserva(
                empresa=self.empresa_con_llave,
                servicio=crear_servicio_pesca(self.empresa_con_llave),
                fecha=date.today() + timedelta(days=10),
                hora=time(6, 0), numero_personas=2, nombre_cliente='Ana',
                telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
                canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
                deslinde_nombre='Ana', checkout_id=uuid.uuid4(), moneda='MXN',
                stripe_payment_intent_id='pi_pendiente',
            )
            reserva.full_clean()
            reserva.save()

        cliente.payment_intents.retrieve.return_value = mock.Mock(status='requires_payment_method')
        call_command('conciliar_pagos', '--dry-run', stdout=StringIO())

        cliente.payment_intents.retrieve.assert_called_once_with('pi_pendiente')

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_conciliar_pagos_hospedaje_crea_ocupacion(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente

        with scope.con_empresa(self.empresa_con_llave):
            servicio = Servicio.objects.create(
                empresa=self.empresa_con_llave,
                nombre='Bungalow',
                slug='bungalow',
                tipo_servicio='hospedaje',
                estrategia_cupo='por_noche',
                precio_base=Decimal('1500.00'),
                activo=True,
            )
            recurso = Recurso.objects.create(
                empresa=self.empresa_con_llave,
                servicio=servicio,
                nombre='Bungalow 1',
                capacidad_maxima=2,
                activo=True,
            )
            reserva = Reserva(
                empresa=self.empresa_con_llave,
                servicio=servicio,
                fecha=date.today() + timedelta(days=10),
                fecha_salida=date.today() + timedelta(days=12),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Mario Conciliar',
                telefono_cliente='+5216121234567',
                correo_cliente='mario@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                deslinde_nombre='Mario Conciliar',
                checkout_id=uuid.uuid4(),
                moneda='MXN',
                precio_total=Decimal('3000.00'),
                forma_pago=Reserva.FormaPago.COMPLETO,
                stripe_payment_intent_id='pi_succeeded_hospedaje',
            )
            reserva.full_clean()
            reserva.save()

        intent_data = {
            'id': 'pi_succeeded_hospedaje',
            'status': 'succeeded',
            'amount_received': 300000,
            'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }
        intent_mock = mock.MagicMock()
        intent_mock.status = 'succeeded'
        intent_mock.id = 'pi_succeeded_hospedaje'
        intent_mock.amount_received = 300000
        intent_mock.currency = 'mxn'
        intent_mock.__getitem__.side_effect = lambda k: intent_data[k]
        cliente.payment_intents.retrieve.return_value = intent_mock

        salida = StringIO()
        call_command('conciliar_pagos', stdout=salida)

        with scope.con_empresa(self.empresa_con_llave):
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
            self.assertEqual(reserva.ocupaciones.count(), 1)
            oc = reserva.ocupaciones.first()
            self.assertEqual(oc.recurso_id, recurso.pk)
            self.assertEqual(oc.fecha_inicio, reserva.fecha)
            self.assertEqual(oc.fecha_fin, reserva.fecha_salida)
            self.assertTrue(oc.ocupa_cupo)



class AplicarPagoCupoHospedajeYPaquetesTests(TestCase):
    """Pruebas de que el pago confirma y crea las ocupaciones y componentes (Tarea 6.3)."""

    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='Sede Pago Cupo', slug='sede-pago-cupo', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Pago Cupo', slug='empresa-pago-cupo',
            stripe_secret_key='sk_test_pago_cupo', stripe_webhook_secret='whsec_pago_cupo',
            stripe_publishable_key='pk_test_pago_cupo',
        )

    def _crear_reserva_hospedaje(self, servicio):
        reserva = Reserva(
            empresa=self.empresa,
            servicio=servicio,
            fecha=date.today() + timedelta(days=10),
            fecha_salida=date.today() + timedelta(days=12),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Carlos Hotel',
            telefono_cliente='+5216121234567',
            correo_cliente='carlos@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            deslinde_nombre='Carlos Hotel',
            checkout_id=uuid.uuid4(),
            moneda='MXN',
            precio_total=Decimal('2000.00'),
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        with scope.con_empresa(self.empresa):
            reserva.full_clean()
            reserva.save()
        return reserva

    def test_servicio_hospedaje_pagado_crea_reserva_ocupacion_con_rango_correcto(self):
        with scope.con_empresa(self.empresa):
            servicio = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Habitación Doble',
                slug='hab-doble',
                tipo_servicio='hospedaje',
                estrategia_cupo='por_noche',
                precio_base=Decimal('1000.00'),
                activo=True,
            )
            recurso = Recurso.objects.create(
                empresa=self.empresa,
                servicio=servicio,
                nombre='Habitación 101',
                capacidad_maxima=2,
                activo=True,
            )
            reserva = self._crear_reserva_hospedaje(servicio)

        intent = {
            'id': 'pi_hospedaje_1',
            'amount_received': 200000,
            'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }

        with scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)
            self.assertEqual(resultado, APLICADO)
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
            ocupaciones = list(reserva.ocupaciones.all())
            self.assertEqual(len(ocupaciones), 1)
            oc = ocupaciones[0]
            self.assertEqual(oc.recurso_id, recurso.pk)
            self.assertEqual(oc.fecha_inicio, reserva.fecha)
            self.assertEqual(oc.fecha_fin, reserva.fecha_salida)
            self.assertTrue(oc.ocupa_cupo)

    def test_paquete_con_componente_hospedaje_crea_ocupacion_y_componentes(self):
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            s_pesca = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Pesca en Panga',
                slug='pesca-panga',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
                precio_base=Decimal('3000.00'),
                activo=True,
            )
            s_hotel = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Hotel Boutique',
                slug='hotel-boutique',
                tipo_servicio='hospedaje',
                estrategia_cupo='por_noche',
                precio_base=Decimal('2000.00'),
                activo=True,
            )
            recurso_hab = Recurso.objects.create(
                empresa=self.empresa,
                servicio=s_hotel,
                nombre='Habitación 201',
                capacidad_maxima=2,
                activo=True,
            )
            paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa,
                nombre='Pesca y Hotel',
                slug='pesca-hotel',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=1)
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_hotel, orden=2)

            reserva = Reserva(
                empresa=self.empresa,
                paquete=paquete,
                fecha=date.today() + timedelta(days=10),
                fecha_salida=date.today() + timedelta(days=12),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Laura Paquete',
                telefono_cliente='+5216121234567',
                correo_cliente='laura@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                deslinde_nombre='Laura Paquete',
                checkout_id=uuid.uuid4(),
                moneda='MXN',
                precio_total=Decimal('5000.00'),
                forma_pago=Reserva.FormaPago.COMPLETO,
            )
            reserva.full_clean()
            reserva.save()

        intent = {
            'id': 'pi_paquete_1',
            'amount_received': 500000,
            'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }

        with scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)
            self.assertEqual(resultado, APLICADO)
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

            # Debe haber creado ocupación para el componente hotel
            self.assertEqual(reserva.ocupaciones.count(), 1)
            oc = reserva.ocupaciones.first()
            self.assertEqual(oc.recurso_id, recurso_hab.pk)
            self.assertTrue(oc.ocupa_cupo)

            # Debe haber creado ReservaPaqueteComponente para ambos componentes
            componentes = list(reserva.componentes.order_by('servicio__nombre'))
            self.assertEqual(len(componentes), 2)
            for comp in componentes:
                self.assertEqual(comp.estado_cupo, ReservaPaqueteComponente.EstadoCupo.OK)

    @mock.patch('apps.bookings.cupo.confirmacion.evaluar_cupo')
    @mock.patch('apps.payments.services.reembolsar')
    def test_paquete_con_componente_sin_cupo_cancela_reembolsa_y_no_deja_huerfanos(self, mock_reembolsar, mock_evaluar):
        mock_reembolsar.return_value = True
        mock_evaluar.return_value = 'sin_panga'

        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            s_hotel = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Hotel Boutique',
                slug='hotel-boutique',
                tipo_servicio='hospedaje',
                estrategia_cupo='por_noche',
                precio_base=Decimal('2000.00'),
                activo=True,
            )
            recurso_hab = Recurso.objects.create(
                empresa=self.empresa,
                servicio=s_hotel,
                nombre='Habitación 201',
                capacidad_maxima=2,
                activo=True,
            )
            s_pesca = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Pesca en Panga',
                slug='pesca-panga',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
                precio_base=Decimal('3000.00'),
                activo=True,
            )
            paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa,
                nombre='Pesca y Hotel',
                slug='pesca-hotel',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            # El orden: hotel primero (orden 1), luego pesca (orden 2)
            # Hotel se crea primero pero pesca falla en confirmacion, el atomic block debe hacer rollback
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_hotel, orden=1)
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=2)

            reserva = Reserva(
                empresa=self.empresa,
                paquete=paquete,
                fecha=date.today() + timedelta(days=10),
                fecha_salida=date.today() + timedelta(days=12),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Pedro Sin Cupo',
                telefono_cliente='+5216121234567',
                correo_cliente='pedro@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                deslinde_nombre='Pedro Sin Cupo',
                checkout_id=uuid.uuid4(),
                moneda='MXN',
                precio_total=Decimal('5000.00'),
                forma_pago=Reserva.FormaPago.COMPLETO,
            )
            reserva.full_clean()
            reserva.save()

        intent = {
            'id': 'pi_sin_cupo_1',
            'amount_received': 500000,
            'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }

        with scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)
            self.assertEqual(resultado, SIN_CUPO_REEMBOLSADO)
            mock_reembolsar.assert_called_once()

            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
            self.assertTrue(reserva.reembolsada)
            self.assertIn('No hay cupo disponible para el componente', reserva.motivo_cancelacion)

            # NO debe quedar ninguna ocupación huérfana
            self.assertEqual(reserva.ocupaciones.count(), 0)
            # NO debe quedar ningún componente huérfano
            self.assertEqual(reserva.componentes.count(), 0)


class TrasladoPagoFixture:
    def setUp(self):
        from apps.fleet.models import PuntoEncuentro, TransporteTarifa

        self.empresa.stripe_secret_key = 'sk_test_traslados'
        self.empresa.stripe_publishable_key = 'pk_test_traslados'
        self.empresa.save()
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslados', slug='traslados',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta', capacidad_maxima=14, permite_anticipo=False,
        )
        self.punto = PuntoEncuentro.objects.create(
            empresa=self.empresa, nombre='Hotel del centro', zona='centro',
        )
        for tipo, zona, minimo, maximo, mxn, usd in (
            ('redondo_aeropuerto', '', 1, 4, '4500.00', '250.00'),
            ('redondo_aeropuerto', '', 5, None, '6000.00', '340.00'),
            ('redondo_actividad', 'centro', 1, None, '1500.00', '90.00'),
            ('redondo_actividad', 'periferia', 1, None, '1800.00', None),
            ('recepcion_aeropuerto', '', 1, None, '2700.00', '150.00'),
        ):
            TransporteTarifa.objects.create(
                empresa=self.empresa, tipo_traslado=tipo, zona=zona,
                personas_min=minimo, personas_max=maximo, precio=mxn, precio_usd=usd,
            )
        self.stripe_mock = self.enterContext(mock.patch('apps.payments.views.configurar_stripe'))
        self.cliente = self.stripe_mock.return_value
        self.cliente.payment_intents.create.side_effect = lambda params, options: intent_falso(
            amount=params['amount'], currency=params['currency'],
        )

    def reserva(self, tipo='redondo_aeropuerto', personas=4, zona='centro', moneda='MXN'):
        from apps.bookings.models import DetalleTransporte

        reserva = Reserva(
            empresa=self.empresa, servicio=self.servicio, checkout_id=uuid.uuid4(),
            fecha=date.today() + timedelta(days=10), hora=time(14), numero_personas=personas,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', moneda=moneda, canal_origen='web',
            deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
        )
        reserva.full_clean()
        reserva.save()
        detalle = DetalleTransporte(
            reserva=reserva, tipo_traslado=tipo, direccion_personalizada='Casa de prueba', zona=zona,
            fecha_regreso=reserva.fecha + timedelta(days=3) if tipo == 'redondo_aeropuerto' else None,
        )
        detalle.full_clean()
        detalle.save()
        return reserva

    def post(self, reserva, **cambios):
        return self.client.post(
            reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
            {'checkout_id': str(reserva.checkout_id), 'forma_pago': 'completo', **cambios},
            content_type='application/json',
        )


class CrearPagoTrasladoTest(TrasladoPagoFixture, ApiTestCase):
    def test_total_por_tipo_zona_tamano_y_moneda(self):
        for tipo, personas, zona, moneda, esperado in (
            ('redondo_aeropuerto', 1, 'centro', 'MXN', '4500.00'),
            ('redondo_aeropuerto', 4, 'periferia', 'MXN', '4500.00'),
            ('redondo_aeropuerto', 5, 'centro', 'MXN', '6000.00'),
            ('redondo_aeropuerto', 14, 'periferia', 'USD', '340.00'),
            ('redondo_actividad', 14, 'centro', 'MXN', '1500.00'),
            ('redondo_actividad', 2, 'periferia', 'MXN', '1800.00'),
            ('redondo_actividad', 3, 'centro', 'USD', '90.00'),
            ('recepcion_aeropuerto', 14, 'periferia', 'MXN', '2700.00'),
        ):
            with self.subTest(tipo=tipo, personas=personas, zona=zona, moneda=moneda):
                reserva = self.reserva(tipo, personas, zona, moneda)
                response = self.post(reserva, precio_total='0.01')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['monto_a_cobrar'], esperado)
                self.assertEqual(response.data['moneda'], moneda)
                self.assertEqual(response.data['publishable_key'], self.empresa.stripe_publishable_key)
                self.stripe_mock.assert_called_with(self.empresa)
                params, options = self.cliente.payment_intents.create.call_args.args
                self.assertEqual(params['amount'], a_centavos(Decimal(esperado)))
                self.assertEqual(params['currency'], moneda.lower())
                self.assertIn('idempotency_key', options)

    def test_congela_detalle_y_pago_completo(self):
        reserva = self.reserva()
        response = self.post(reserva)
        self.assertEqual(response.status_code, 200, response.data)
        reserva.refresh_from_db()
        self.assertEqual(response.data['monto_a_cobrar'], '4500.00')
        self.assertEqual(reserva.detalle_transporte.numero_personas, 4)
        self.assertEqual(reserva.detalle_transporte.precio_calculado, Decimal('4500.00'))
        self.assertEqual(reserva.precio_total, Decimal('4500.00'))
        self.assertEqual(reserva.forma_pago, 'completo')
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    def test_zona_efectiva_del_punto(self):
        reserva = self.reserva('redondo_actividad')
        detalle = reserva.detalle_transporte
        detalle.punto_encuentro = self.punto
        detalle.direccion_personalizada = ''
        detalle.zona = 'centro'
        detalle.full_clean()
        detalle.save()
        response = self.post(reserva)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['monto_a_cobrar'], '1500.00')

    def test_reintento_reutiliza_intent_y_cambio_de_tamano_lo_actualiza(self):
        reserva = self.reserva()
        first = self.post(reserva)
        self.assertEqual(first.status_code, 200, first.data)
        self.cliente.payment_intents.retrieve.return_value = intent_falso()
        self.assertEqual(self.post(reserva).status_code, 200)
        self.cliente.payment_intents.create.assert_called_once()
        self.cliente.payment_intents.update.assert_not_called()
        reserva.refresh_from_db()
        reserva.numero_personas = 5
        reserva.save()
        self.cliente.payment_intents.update.return_value = intent_falso(amount=600000)
        self.assertEqual(self.post(reserva).status_code, 200)
        self.cliente.payment_intents.update.assert_called_once_with('pi_1', {'amount': 600000, 'currency': 'mxn'})
        reserva.refresh_from_db()
        self.assertEqual(reserva.detalle_transporte.numero_personas, 5)
        self.assertEqual(reserva.detalle_transporte.precio_calculado, Decimal('6000.00'))

    def test_intent_cobrando_no_recongela_ni_crea_otro(self):
        reserva = self.reserva()
        self.assertEqual(self.post(reserva).status_code, 200)
        reserva.refresh_from_db()
        reserva.numero_personas = 5
        reserva.save()
        for estado in ('succeeded', 'processing'):
            self.cliente.payment_intents.retrieve.return_value = intent_falso(status=estado)
            self.assertEqual(self.post(reserva).status_code, 409)
        self.cliente.payment_intents.create.assert_called_once()
        reserva.refresh_from_db()
        self.assertEqual(reserva.detalle_transporte.numero_personas, 4)
        self.assertEqual(reserva.precio_total, Decimal('4500.00'))

    def test_tarifa_inactiva_usd_ausente_y_detalle_ausente_no_cobran(self):
        from apps.fleet.models import TransporteTarifa

        sin_usd = self.reserva('redondo_actividad', zona='periferia', moneda='USD')
        self.assertEqual(self.post(sin_usd).status_code, 503)
        reserva = self.reserva()
        TransporteTarifa.objects.filter(tipo_traslado='redondo_aeropuerto').update(activo=False)
        self.assertEqual(self.post(reserva).status_code, 503)
        reserva.detalle_transporte.delete()
        self.assertEqual(self.post(reserva).status_code, 503)
        self.cliente.payment_intents.create.assert_not_called()

    def test_fallo_stripe_no_congela(self):
        reserva = self.reserva()
        self.cliente.payment_intents.create.side_effect = stripe.APIConnectionError('sin red')
        self.assertEqual(self.post(reserva).status_code, 502)
        reserva.refresh_from_db()
        self.assertIsNone(reserva.detalle_transporte.precio_calculado)
        self.assertIsNone(reserva.detalle_transporte.numero_personas)
        self.assertIsNone(reserva.precio_total)

    def test_verificar_monto_usa_demanda_y_precio_congelados(self):
        from apps.fleet.models import TransporteTarifa
        from .estrategias_precio import obtener_estrategia_precio
        from .services import _verificar_monto

        reserva = self.reserva()
        self.assertEqual(self.post(reserva).status_code, 200)
        reserva.refresh_from_db()
        # El catalogo y el grupo operativo pueden cambiar tras preparar el cobro.
        TransporteTarifa.objects.update(precio='9999.00', activo=False)
        reserva.numero_personas = 14
        estrategia = obtener_estrategia_precio('por_ruta')
        with mock.patch.object(estrategia, 'calcular_base', wraps=estrategia.calcular_base) as calcular:
            with self.assertNoLogs('apps.payments.services', level='ERROR'):
                _verificar_monto(reserva, {'currency': 'mxn', 'amount_received': 450000})
            self.assertEqual(calcular.call_args.args[1].personas, 4)
            self.assertEqual(calcular.call_args.args[1].tipo_traslado, 'redondo_aeropuerto')
            self.assertEqual(calcular.call_args.args[1].zona, '')
        with self.assertLogs('apps.payments.services', level='ERROR') as logs:
            _verificar_monto(reserva, {'currency': 'mxn', 'amount_received': 449999})
        self.assertIn('Descuadre', ' '.join(logs.output))

    def test_verificar_total_descontado_del_precio_congelado(self):
        from .services import _verificar_monto

        reserva = self.reserva()
        self.assertEqual(self.post(reserva).status_code, 200)
        reserva.refresh_from_db()
        reserva.descuento_aplicado = Decimal('450.00')
        reserva.precio_total = Decimal('4050.00')
        with self.assertNoLogs('apps.payments.services', level='ERROR'):
            _verificar_monto(reserva, {'currency': 'mxn', 'amount_received': 405000})
        reserva.precio_total = Decimal('4000.00')
        with self.assertLogs('apps.payments.services', level='ERROR'):
            _verificar_monto(reserva, {'currency': 'mxn', 'amount_received': 400000})


@override_settings(
    RESEND_API_KEY='resend_test', RESEND_FROM='reservas@example.com', RESEND_BCC=[],
    WHATSAPP_TOKEN='whatsapp_test', WHATSAPP_PHONE_NUMBER_ID='12345',
)
class WebhookTrasladoTest(TrasladoPagoFixture, ApiTestCase):
    def confirmar(self, reserva):
        evento = evento_pagado(reserva.pk)
        with mock.patch('apps.payments.views.stripe.Webhook.construct_event', return_value=evento):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post(
                    f'/api/{self.empresa.slug}/stripe/webhook/', data='{}',
                    content_type='application/json', HTTP_STRIPE_SIGNATURE='firma_simulada',
                )

    @mock.patch('apps.notifications.services.requests.post')
    def test_webhook_pagada_sin_cupo_y_correo_de_traslado_una_sola_vez(self, post):
        reserva = self.reserva()
        detalle = reserva.detalle_transporte
        detalle.punto_encuentro = self.punto
        detalle.direccion_personalizada = ''
        detalle.full_clean()
        detalle.save()
        self.assertEqual(self.post(reserva).status_code, 200)
        with mock.patch('apps.bookings.models.validar_cupo_diario') as cupo:
            with mock.patch('apps.bookings.cupo.confirmacion.bloquear_cupo') as candado:
                self.assertEqual(self.confirmar(reserva).status_code, 200)
                self.assertEqual(self.confirmar(reserva).status_code, 200)
        cupo.assert_not_called()
        candado.assert_not_called()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.monto_pagado, Decimal('4500.00'))
        self.assertFalse(ReservaOcupacion.objects.filter(reserva=reserva).exists())
        self.assertFalse(ReservaPaqueteComponente.objects.filter(reserva=reserva).exists())
        self.assertIsNone(reserva.embarcacion_id)
        self.assertIsNone(reserva.capitan_id)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], 'https://api.resend.com/emails')
        cuerpo = post.call_args.kwargs['json']['html']
        self.assertIn('Hotel del centro', cuerpo)
        self.assertIn(detalle.get_tipo_traslado_display(), cuerpo)
        self.assertIn(str(detalle.fecha_regreso), cuerpo)
        self.assertNotIn('capitan', cuerpo.lower())
        self.assertNotIn('panga', cuerpo.lower())
        self.assertNotIn('Marina La Costa', cuerpo)

    @mock.patch('apps.notifications.services.requests.post')
    def test_correo_escapa_direccion_personalizada(self, post):
        from apps.notifications.services import notificar_reserva_pagada

        reserva = self.reserva('redondo_actividad')
        detalle = reserva.detalle_transporte
        detalle.direccion_personalizada = 'Casa <b>Azul</b> & patio'
        detalle.save()
        resultado = notificar_reserva_pagada(reserva)
        self.assertEqual(resultado, {'email': True, 'whatsapp': False})
        cuerpo = post.call_args.kwargs['json']['html']
        self.assertIn('Casa &lt;b&gt;Azul&lt;/b&gt; &amp; patio', cuerpo)
        self.assertNotIn('<b>Azul</b>', cuerpo)
        self.assertNotIn('capitan', cuerpo.lower())
        post.assert_called_once()

    @mock.patch('apps.notifications.services.requests.post')
    def test_fallo_de_correo_no_revierte_pago_ni_ocupa_cupo(self, post):
        import requests

        post.side_effect = requests.RequestException('correo no disponible')
        reserva = self.reserva()
        self.assertEqual(self.post(reserva).status_code, 200)
        self.assertEqual(self.confirmar(reserva).status_code, 200)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertFalse(reserva.ocupaciones.exists())
        self.assertFalse(reserva.componentes.exists())
        self.assertFalse(reserva.reembolsada)
        post.assert_called_once()

    @mock.patch('apps.notifications.services.requests.post')
    def test_descuadre_se_registra_pero_webhook_confirma(self, post):
        reserva = self.reserva()
        self.assertEqual(self.post(reserva).status_code, 200)
        Reserva.objects.filter(pk=reserva.pk).update(precio_total='1.00')
        with self.assertLogs('apps.payments.services', level='ERROR'):
            self.assertEqual(self.confirmar(reserva).status_code, 200)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertFalse(reserva.ocupaciones.exists())


class MontoPorEmpresaTest(TestCase):
    def test_reparto_exitoso(self):
        # paquete $5000, transporte $2700 -> {empresa1: 2300, empresa2: 2700}
        componentes = [
            {'empresa_id': 1, 'es_lider': True, 'monto_fijo': None},
            {'empresa_id': 2, 'es_lider': False, 'monto_fijo': Decimal('2700.00')},
        ]
        reparto = monto_por_empresa(precio_paquete=Decimal('5000.00'), componentes=componentes, moneda='MXN')
        self.assertEqual(reparto, {1: Decimal('2300.00'), 2: Decimal('2700.00')})

    def test_precio_menor_a_transporte_lanza_value_error(self):
        # precio $2000 < transporte $2700 -> ValueError
        componentes = [
            {'empresa_id': 1, 'es_lider': True, 'monto_fijo': None},
            {'empresa_id': 2, 'es_lider': False, 'monto_fijo': Decimal('2700.00')},
        ]
        with self.assertRaises(ValueError):
            monto_por_empresa(precio_paquete=Decimal('2000.00'), componentes=componentes, moneda='MXN')

    def test_dos_componentes_sin_monto_fijo_lanza_value_error(self):
        # dos componentes sin monto_fijo -> ValueError
        componentes = [
            {'empresa_id': 1, 'es_lider': True, 'monto_fijo': None},
            {'empresa_id': 2, 'es_lider': False, 'monto_fijo': None},
        ]
        with self.assertRaises(ValueError):
            monto_por_empresa(precio_paquete=Decimal('5000.00'), componentes=componentes, moneda='MXN')

    def test_cero_componentes_lider_lanza_value_error(self):
        componentes = [
            {'empresa_id': 1, 'es_lider': False, 'monto_fijo': Decimal('2000.00')},
            {'empresa_id': 2, 'es_lider': False, 'monto_fijo': Decimal('2700.00')},
        ]
        with self.assertRaises(ValueError):
            monto_por_empresa(precio_paquete=Decimal('5000.00'), componentes=componentes, moneda='MXN')


class CrearOrdenTest(TestCase):
    def setUp(self):
        super().setUp()
        from apps.bookings.models import DetalleTransporte, Orden, Reserva
        from apps.fleet.enums import TipoTraslado
        from apps.fleet.models import Paquete, PaqueteServicio, Servicio, TransporteTarifa
        from apps.tenancy.models import Empresa, Sede

        self.sede = Sede.objects.create(nombre='Sede Test', slug='sede-test', activo=True)
        self.empresa_lider = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Pesca', slug='empresa-pesca', activo=True
        )
        self.empresa_transporte = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Transporte', slug='empresa-transporte', activo=True
        )

        with scope.como_operador_plataforma():
            self.servicio_pesca = Servicio.objects.create(
                empresa=self.empresa_lider,
                nombre='Pesca Mayor',
                slug='pesca-mayor',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
                precio_base=Decimal('4000.00'),
            )
            self.servicio_transporte = Servicio.objects.create(
                empresa=self.empresa_transporte,
                nombre='Traslado Aeropuerto',
                slug='traslado-aeropuerto',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
                estrategia_precio='por_ruta',
            )
            self.tarifa_transporte = TransporteTarifa.objects.create(
                empresa=self.empresa_transporte,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1,
                personas_max=4,
                precio=Decimal('2000.00'),
                precio_usd=Decimal('120.00'),
            )
            self.paquete_cruza = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_lider,
                nombre='Pesca y Traslado',
                slug='pesca-y-traslado',
                precio_ancla=Decimal('5000.00'),
                precio_ancla_usd=Decimal('300.00'),
                permite_anticipo=False,
            )
            PaqueteServicio.objects.create(paquete=self.paquete_cruza, servicio=self.servicio_pesca, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete_cruza, servicio=self.servicio_transporte, orden=2)

            self.paquete_mono = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_lider,
                nombre='Solo Pesca Paquete',
                slug='solo-pesca-paquete',
                precio_ancla=Decimal('4000.00'),
            )
            PaqueteServicio.objects.create(paquete=self.paquete_mono, servicio=self.servicio_pesca, orden=1)

        from django.contrib.auth.models import User
        from apps.bookings.models import Vendedora
        with scope.como_operador_plataforma():
            u = User.objects.create_user('vendedora_test', 'v@test.com', 'pass')
            self.vendedora = Vendedora.objects.create(usuario=u, empresa=self.empresa_lider, codigo='amigo')

    def test_crear_orden_exitosa(self):
        from apps.bookings.models import DetalleTransporte, Orden, Reserva
        from apps.fleet.enums import TipoTraslado

        payload = {
            'checkout_id': str(uuid.uuid4()),
            'paquete': self.paquete_cruza.slug,
            'nombre_cliente': 'Carlos Lopez',
            'telefono_cliente': '1234567890',
            'correo_cliente': 'carlos@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Lopez',
            'ref': 'amigo',
            'fecha': '2026-10-15',
            'hora': '07:00:00',
            'componentes': [
                {'servicio': self.servicio_pesca.slug, 'numero_personas': 2},
                {'servicio': self.servicio_transporte.slug, 'numero_personas': 2},
            ],
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'direccion_personalizada': 'Calle Marina 123',
            'fecha_regreso': '2026-10-17',
        }
        url = f'/api/{self.sede.slug}/ordenes/'
        res = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('orden_id', data)
        self.assertEqual(data['estado'], 'armando')
        self.assertEqual(len(data['reservas']), 2)

        with scope.como_operador_plataforma():
            orden = Orden.objects.get(pk=data['orden_id'])
            self.assertEqual(orden.estado, Orden.Estado.ARMANDO)
            self.assertEqual(orden.empresa_lider, self.empresa_lider)
            self.assertEqual(orden.paquete, self.paquete_cruza)

            reservas = list(Reserva.objects.filter(orden=orden).order_by('id'))
            self.assertEqual(len(reservas), 2)
            r_lider = next(r for r in reservas if r.empresa_id == self.empresa_lider.id)
            r_trans = next(r for r in reservas if r.empresa_id == self.empresa_transporte.id)

            self.assertEqual(r_lider.paquete, self.paquete_cruza)
            self.assertEqual(r_lider.servicio, self.servicio_pesca)
            self.assertEqual(r_lider.vendedora, self.vendedora)
            self.assertTrue(r_lider.deslinde_aceptado)

            self.assertIsNone(r_trans.paquete)
            self.assertEqual(r_trans.servicio, self.servicio_transporte)
            self.assertIsNone(r_trans.vendedora)
            self.assertTrue(r_trans.deslinde_aceptado)

            detalle = DetalleTransporte.objects.get(reserva=r_trans)
            self.assertEqual(detalle.tipo_traslado, TipoTraslado.REDONDO_AEROPUERTO)
            self.assertEqual(detalle.direccion_personalizada, 'Calle Marina 123')
            self.assertEqual(str(detalle.fecha_regreso), '2026-10-17')

    def test_paquete_mono_empresa_retorna_400(self):
        payload = {
            'checkout_id': str(uuid.uuid4()),
            'paquete': self.paquete_mono.slug,
            'nombre_cliente': 'Carlos Lopez',
            'telefono_cliente': '1234567890',
            'correo_cliente': 'carlos@example.com',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Lopez',
            'fecha': '2026-10-15',
            'hora': '07:00:00',
            'componentes': [
                {'servicio': self.servicio_pesca.slug, 'numero_personas': 2},
            ],
        }
        res = self.client.post(f'/api/{self.sede.slug}/ordenes/', payload, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('cruza-empresa', str(res.json()))

    def test_deslinde_faltante_o_no_aceptado_retorna_400(self):
        payload = {
            'checkout_id': str(uuid.uuid4()),
            'paquete': self.paquete_cruza.slug,
            'nombre_cliente': 'Carlos Lopez',
            'telefono_cliente': '1234567890',
            'correo_cliente': 'carlos@example.com',
            'deslinde_aceptado': False,
            'fecha': '2026-10-15',
            'hora': '07:00:00',
            'numero_personas': 2,
        }
        res = self.client.post(f'/api/{self.sede.slug}/ordenes/', payload, content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_reutiliza_orden_por_checkout_id_en_armando_o_autorizando(self):
        from apps.bookings.models import Orden
        from apps.fleet.enums import TipoTraslado

        cid = str(uuid.uuid4())
        payload = {
            'checkout_id': cid,
            'paquete': self.paquete_cruza.slug,
            'nombre_cliente': 'Carlos Lopez',
            'telefono_cliente': '1234567890',
            'correo_cliente': 'carlos@example.com',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Lopez',
            'fecha': '2026-10-15',
            'hora': '07:00:00',
            'componentes': [
                {'servicio': self.servicio_pesca.slug, 'numero_personas': 2},
                {'servicio': self.servicio_transporte.slug, 'numero_personas': 2},
            ],
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'direccion_personalizada': 'Calle Marina 123',
            'fecha_regreso': '2026-10-17',
        }
        res1 = self.client.post(f'/api/{self.sede.slug}/ordenes/', payload, content_type='application/json')
        self.assertEqual(res1.status_code, 201)
        orden_id_1 = res1.json()['orden_id']

        payload['nombre_cliente'] = 'Carlos Lopez Actualizado'
        res2 = self.client.post(f'/api/{self.sede.slug}/ordenes/', payload, content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()['orden_id'], orden_id_1)

        with scope.como_operador_plataforma():
            orden = Orden.objects.get(pk=orden_id_1)
            self.assertEqual(orden.nombre_cliente, 'Carlos Lopez Actualizado')

    def test_ignora_orden_capturada_con_mismo_checkout_id(self):
        from apps.bookings.models import Orden
        from apps.fleet.enums import TipoTraslado

        cid = str(uuid.uuid4())
        with scope.con_empresa(self.empresa_lider):
            Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_lider,
                paquete=self.paquete_cruza,
                checkout_id=cid,
                nombre_cliente='Antiguo',
                telefono_cliente='1234567890',
                correo_cliente='antiguo@example.com',
                estado=Orden.Estado.CAPTURADA,
            )
        payload = {
            'checkout_id': cid,
            'paquete': self.paquete_cruza.slug,
            'nombre_cliente': 'Nuevo Cliente',
            'telefono_cliente': '1234567890',
            'correo_cliente': 'nuevo@example.com',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Nuevo Cliente',
            'fecha': '2026-10-15',
            'hora': '07:00:00',
            'componentes': [
                {'servicio': self.servicio_pesca.slug, 'numero_personas': 2},
                {'servicio': self.servicio_transporte.slug, 'numero_personas': 2},
            ],
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'direccion_personalizada': 'Calle Marina 123',
            'fecha_regreso': '2026-10-17',
        }
        res = self.client.post(f'/api/{self.sede.slug}/ordenes/', payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        with scope.como_operador_plataforma():
            nueva_orden = Orden.objects.get(pk=res.json()['orden_id'])
            self.assertEqual(nueva_orden.estado, Orden.Estado.ARMANDO)
            self.assertEqual(nueva_orden.nombre_cliente, 'Nuevo Cliente')


class OrdenesModuloTest(TestCase):
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_revertir_capturada_rechaza_antes_de_tocar_stripe(self, configurar):
        from apps.payments.ordenes import OrdenCerradaError, revertir_orden

        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.CAPTURADA
            self.orden.save(update_fields=['estado'])
        with self.assertRaises(OrdenCerradaError):
            revertir_orden(self.orden, 'cancelación tardía')
        configurar.assert_not_called()

    def setUp(self):
        from apps.bookings.models import Orden, Reserva
        from apps.fleet.models import Paquete, PaqueteServicio, Servicio
        from apps.tenancy.models import Empresa, Sede

        self.sede = Sede.objects.create(nombre='Sede Modulo', slug='sede-modulo-test', activo=True)
        self.empresa_1 = Empresa.objects.create(
            nombre='Empresa Pesca Mod',
            slug='emp-mod-pesca',
            sede=self.sede,
            stripe_secret_key='sk_test_1',
            stripe_publishable_key='pk_test_1',
        )
        self.empresa_2 = Empresa.objects.create(
            nombre='Empresa Transporte Mod',
            slug='emp-mod-transporte',
            sede=self.sede,
            stripe_secret_key='sk_test_2',
            stripe_publishable_key='pk_test_2',
        )
        with scope.como_operador_plataforma():
            self.servicio_1 = Servicio.objects.create(
                empresa=self.empresa_1,
                nombre='Pesca Mod',
                slug='pesca-mod',
                tipo_servicio='pesca',
            )
            self.servicio_2 = Servicio.objects.create(
                empresa=self.empresa_2,
                nombre='Transporte Mod',
                slug='transporte-mod',
                tipo_servicio='transporte',
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                nombre='Paquete Modulo',
                slug='paquete-modulo',
                precio_ancla=Decimal('10000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_1, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_2, orden=2)

        with scope.con_empresa(self.empresa_1):
            self.orden = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                paquete=self.paquete,
                nombre_cliente='Cliente Prueba',
                telefono_cliente='1234567890',
                correo_cliente='cliente@example.com',
                moneda='MXN',
                estado=Orden.Estado.ARMANDO,
            )
            self.reserva_1 = Reserva.objects.create(
                empresa=self.empresa_1,
                servicio=self.servicio_1,
                paquete=self.paquete,
                orden=self.orden,
                fecha=date(2026, 10, 15),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Prueba',
                telefono_cliente='1234567890',
                correo_cliente='cliente@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2 = Reserva.objects.create(
                empresa=self.empresa_2,
                servicio=self.servicio_2,
                paquete=None,
                orden=self.orden,
                fecha=date(2026, 10, 15),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Prueba',
                telefono_cliente='1234567890',
                correo_cliente='cliente@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
            )

        self.reparto = {
            self.empresa_1.id: Decimal('7000.00'),
            self.empresa_2.id: Decimal('3000.00'),
        }

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_crear_pagos_orden_crea_intents_correctos(self, mock_configurar_stripe):
        from apps.payments.ordenes import crear_pagos_orden

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()

        def _get_client(empresa):
            return cliente_1 if empresa.id == self.empresa_1.id else cliente_2

        mock_configurar_stripe.side_effect = _get_client

        intent_1 = mock.Mock(id='pi_1', client_secret='pi_1_sec', status='requires_capture')
        intent_2 = mock.Mock(id='pi_2', client_secret='pi_2_sec', status='requires_capture')
        cliente_1.payment_intents.create.return_value = intent_1
        cliente_2.payment_intents.create.return_value = intent_2

        resultado = crear_pagos_orden(self.orden, self.reparto)

        self.assertEqual(len(resultado), 2)
        # Check client_1 call
        c1_call = cliente_1.payment_intents.create.call_args
        self.assertEqual(c1_call.args[0]['amount'], 700000)
        self.assertEqual(c1_call.args[0]['capture_method'], 'manual')
        self.assertEqual(c1_call.args[0]['payment_method_types'], ['card'])
        self.assertEqual(c1_call.args[1]['idempotency_key'], f'orden-{self.orden.id}-{self.empresa_1.id}-crear')

        # Check client_2 call
        c2_call = cliente_2.payment_intents.create.call_args
        self.assertEqual(c2_call.args[0]['amount'], 300000)
        self.assertEqual(c2_call.args[0]['capture_method'], 'manual')
        self.assertEqual(c2_call.args[0]['payment_method_types'], ['card'])
        self.assertEqual(c2_call.args[1]['idempotency_key'], f'orden-{self.orden.id}-{self.empresa_2.id}-crear')

        with scope.como_operador_plataforma():
            self.reserva_1.refresh_from_db()
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_1.stripe_payment_intent_id, 'pi_1')
            self.assertEqual(self.reserva_2.stripe_payment_intent_id, 'pi_2')

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_crear_pagos_orden_idempotente(self, mock_configurar_stripe):
        from apps.payments.ordenes import crear_pagos_orden

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        intent_1 = mock.Mock(id='pi_1', client_secret='pi_1_sec', status='requires_capture', amount=700000, currency='mxn')
        intent_2 = mock.Mock(id='pi_2', client_secret='pi_2_sec', status='requires_capture', amount=300000, currency='mxn')
        cliente_1.payment_intents.create.return_value = intent_1
        cliente_2.payment_intents.create.return_value = intent_2
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        # 1st call
        res_1 = crear_pagos_orden(self.orden, self.reparto)
        self.assertEqual(cliente_1.payment_intents.create.call_count, 1)
        self.assertEqual(cliente_2.payment_intents.create.call_count, 1)

        # 2nd call
        res_2 = crear_pagos_orden(self.orden, self.reparto)
        # Create should not be called again
        self.assertEqual(cliente_1.payment_intents.create.call_count, 1)
        self.assertEqual(cliente_2.payment_intents.create.call_count, 1)

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_actualizar_intent_reintenta_con_la_misma_clave(self, configurar):
        from apps.payments.ordenes import crear_pagos_orden

        clientes = {e.id: mock.Mock() for e in (self.empresa_1, self.empresa_2)}
        configurar.side_effect = lambda empresa: clientes[empresa.id]
        for empresa, reserva in ((self.empresa_1, self.reserva_1), (self.empresa_2, self.reserva_2)):
            pi_id = f'pi_{empresa.id}'
            with scope.con_empresa(empresa):
                Reserva.objects.filter(pk=reserva.pk).update(stripe_payment_intent_id=pi_id)
            clientes[empresa.id].payment_intents.retrieve.return_value = mock.Mock(
                id=pi_id, status='requires_payment_method', amount=100, currency='mxn',
            )
            clientes[empresa.id].payment_intents.update.return_value = mock.Mock(
                id=pi_id, client_secret='secret',
            )
        crear_pagos_orden(self.orden, self.reparto)
        crear_pagos_orden(self.orden, self.reparto)
        for empresa_id, monto in self.reparto.items():
            centavos = a_centavos(monto)
            self.assertEqual(clientes[empresa_id].payment_intents.update.call_args_list, [
                mock.call(
                    f'pi_{empresa_id}', {'amount': centavos, 'currency': 'mxn'},
                    {'idempotency_key': f'orden-{self.orden.id}-{empresa_id}-update-mxn-100-{centavos}'},
                ),
            ] * 2)
            clientes[empresa_id].payment_intents.create.assert_not_called()

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_crear_pagos_orden_fallo_parcial_propaga_y_conserva_primero(self, mock_configurar_stripe):
        from apps.payments.ordenes import crear_pagos_orden

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        intent_1 = mock.Mock(id='pi_1', client_secret='pi_1_sec', status='requires_capture')
        cliente_1.payment_intents.create.return_value = intent_1
        cliente_2.payment_intents.create.side_effect = stripe.StripeError('Error simulado en empresa 2')

        with self.assertRaises(stripe.StripeError):
            crear_pagos_orden(self.orden, self.reparto)

        with scope.como_operador_plataforma():
            self.reserva_1.refresh_from_db()
            self.reserva_2.refresh_from_db()
            # Reserva 1 conservó su PI
            self.assertEqual(self.reserva_1.stripe_payment_intent_id, 'pi_1')
            # Reserva 2 quedó vacía
            self.assertEqual(self.reserva_2.stripe_payment_intent_id, '')

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_crear_pagos_orden_rechaza_si_orden_cerrada(self, mock_configurar_stripe):
        from apps.payments.ordenes import OrdenCerradaError, crear_pagos_orden

        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.CAPTURADA
            self.orden.save(update_fields=['estado'])

        with self.assertRaises(OrdenCerradaError):
            crear_pagos_orden(self.orden, self.reparto)

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_exitoso(self, mock_configurar_stripe):
        from apps.payments.ordenes import confirmar_captura

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='requires_capture')
        intent_2 = mock.Mock(id='pi_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        confirmar_captura(self.orden)

        cliente_1.payment_intents.capture.assert_called_once_with(
            'pi_1', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_1.id}-capture'},
        )
        cliente_2.payment_intents.capture.assert_called_once_with(
            'pi_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-capture'},
        )

        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            # No marca capturada: eso lo hace el webhook
            self.assertNotEqual(self.orden.estado, Orden.Estado.CAPTURADA)

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_con_pi_ya_succeeded_se_salta(self, mock_configurar_stripe):
        from apps.payments.ordenes import confirmar_captura

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='succeeded')
        intent_2 = mock.Mock(id='pi_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        confirmar_captura(self.orden)

        cliente_1.payment_intents.capture.assert_not_called()
        cliente_2.payment_intents.capture.assert_called_once_with(
            'pi_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-capture'},
        )

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_revierte_si_uno_no_esta_requires_capture(self, mock_configurar_stripe):
        from apps.payments.ordenes import confirmar_captura

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='requires_confirmation')
        intent_2 = mock.Mock(id='pi_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        confirmar_captura(self.orden)

        # Никакой capture не должен вызываться
        cliente_1.payment_intents.capture.assert_not_called()
        cliente_2.payment_intents.capture.assert_not_called()

        # Debe haberse revertido la orden
        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)
        # pi_2 (requires_capture) debe haberse cancelado
        cliente_2.payment_intents.cancel.assert_called_once_with(
            'pi_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-cancel'},
        )

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_revertir_orden_cancela_pendientes_y_reembolsa_succeeded(self, mock_configurar_stripe):
        from apps.payments.ordenes import revertir_orden
        from apps.bookings.models import ReservaPaqueteComponente

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.estado = Reserva.Estado.PAGADA
            self.reserva_1.save(update_fields=['stripe_payment_intent_id', 'estado'])
            componente = ReservaPaqueteComponente.objects.create(
                reserva=self.reserva_1, servicio=self.reserva_1.servicio,
                empresa=self.empresa_1, estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='succeeded')
        intent_2 = mock.Mock(id='pi_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        revertir_orden(self.orden, 'motivo de prueba')

        # intent_1 (succeeded) -> refund
        cliente_1.refunds.create.assert_called_once_with(
            {'payment_intent': 'pi_1'},
            {'idempotency_key': f'orden-{self.orden.id}-{self.empresa_1.id}-refund'},
        )
        # intent_2 (requires_capture) -> cancel
        cliente_2.payment_intents.cancel.assert_called_once_with(
            'pi_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-cancel'},
        )

        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

            self.reserva_1.refresh_from_db()
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.CANCELADA)
            self.assertEqual(self.reserva_1.motivo_cancelacion, 'motivo de prueba')
            self.assertTrue(self.reserva_1.reembolsada)
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.CANCELADA)
            self.assertEqual(self.reserva_2.motivo_cancelacion, 'motivo de prueba')
            self.assertFalse(self.reserva_2.reembolsada)
            componente.refresh_from_db()
            self.assertEqual(componente.estado_cupo, ReservaPaqueteComponente.EstadoCupo.LIBERADO)

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_revertir_orden_idempotente(self, mock_configurar_stripe):
        from apps.payments.ordenes import revertir_orden

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='succeeded')
        intent_2 = mock.Mock(id='pi_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        revertir_orden(self.orden, 'motivo')
        # Segunda llamada con intents ya canceled/refunded
        intent_1.status = 'refunded'
        intent_2.status = 'canceled'
        # No debe lanzar error ni intentar re-cancelar/re-reembolsar
        revertir_orden(self.orden, 'motivo')
        self.assertEqual(cliente_1.refunds.create.call_count, 1)
        self.assertEqual(cliente_2.payment_intents.cancel.call_count, 1)

    @mock.patch('apps.payments.ordenes.time.sleep')
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_parcial_reintenta_y_revierte_con_refund(self, mock_configurar_stripe, mock_sleep):
        """Tarea 5.3: mock: captura 1 OK, captura 2 falla 3 veces -> refund de 1, cancel de 2, orden cancelada."""
        from apps.payments.ordenes import confirmar_captura
        from apps.bookings.orden_lectura import reservas_de_orden

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='requires_capture', amount=700000)
        intent_2 = mock.Mock(id='pi_2', status='requires_capture', amount=300000)
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        def capture_1(pi_id, *, options):
            intent_1.status = 'succeeded'
            return mock.Mock()

        cliente_1.payment_intents.capture.side_effect = capture_1
        cliente_2.payment_intents.capture.side_effect = stripe.CardError(
            message='Tarjeta rechazada', param='card', code='card_declined'
        )

        # Este escenario necesita una captura exitosa ANTES de la fallida.
        # SECURITY DEFINER no promete orden SQL; conserva la lectura real y
        # fija solo el orden de las filas para construir esa captura parcial.
        def filas_captura_parcial(orden_id):
            return sorted(reservas_de_orden(orden_id), key=lambda fila: fila['reserva_id'])

        with mock.patch('apps.payments.ordenes.reservas_de_orden', side_effect=filas_captura_parcial):
            with self.assertLogs('apps.payments.ordenes', level='ERROR') as cm:
                confirmar_captura(self.orden)

        cliente_1.payment_intents.capture.assert_called_once_with(
            'pi_1', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_1.id}-capture'},
        )
        self.assertEqual(cliente_2.payment_intents.capture.call_args_list, [
            mock.call('pi_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-capture'})
        ] * 3)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertTrue(any('no se pudo capturar' in m.lower() for m in cm.output))

        cliente_1.refunds.create.assert_called_once_with(
            {'payment_intent': 'pi_1'},
            {'idempotency_key': f'orden-{self.orden.id}-{self.empresa_1.id}-refund'},
        )
        cliente_2.payment_intents.cancel.assert_called_once_with(
            'pi_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-cancel'},
        )

        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

            self.reserva_1.refresh_from_db()
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.CANCELADA)
            self.assertTrue(self.reserva_1.reembolsada)
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.CANCELADA)
            self.assertFalse(self.reserva_2.reembolsada)

    @mock.patch('apps.payments.ordenes.time.sleep')
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_reintenta_y_logra_capturar(self, mock_configurar_stripe, mock_sleep):
        """Si un intento falla pero el reintento tiene éxito, la orden no se revierte."""
        from apps.payments.ordenes import confirmar_captura

        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_1', status='requires_capture', amount=700000)
        intent_2 = mock.Mock(id='pi_2', status='requires_capture', amount=300000)
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        # Empresa 1 captura a la primera
        cliente_1.payment_intents.capture.return_value = mock.Mock()
        # Empresa 2 falla el primer intento, tiene éxito en el segundo
        intent_2_captured = mock.Mock(id='pi_2', status='succeeded')
        cliente_2.payment_intents.capture.side_effect = [
            stripe.StripeError('Network glitch'),
            intent_2_captured,
        ]

        confirmar_captura(self.orden)

        self.assertEqual(cliente_1.payment_intents.capture.call_count, 1)
        self.assertEqual(cliente_2.payment_intents.capture.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

        # No debe haberse revertido
        cliente_1.refunds.create.assert_not_called()
        cliente_2.payment_intents.cancel.assert_not_called()
        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertNotEqual(self.orden.estado, Orden.Estado.CANCELADA)




class OrdenesApiTest(TestCase):
    def setUp(self):
        from apps.bookings.models import DetalleTransporte, Orden, Reserva
        from apps.fleet.enums import TipoTraslado
        from apps.fleet.models import Paquete, PaqueteServicio, Servicio, TransporteTarifa
        from apps.tenancy.models import Empresa, Sede

        self.sede = Sede.objects.create(nombre='Sede API', slug='sede-api-ordenes', activo=True)
        self.empresa_1 = Empresa.objects.create(
            nombre='Empresa Pesca API',
            slug='emp-api-pesca',
            sede=self.sede,
            stripe_secret_key='sk_test_api_1',
            stripe_publishable_key='pk_test_api_1',
        )
        self.empresa_2 = Empresa.objects.create(
            nombre='Empresa Transporte API',
            slug='emp-api-transporte',
            sede=self.sede,
            stripe_secret_key='sk_test_api_2',
            stripe_publishable_key='pk_test_api_2',
        )
        with scope.como_operador_plataforma():
            self.servicio_1 = Servicio.objects.create(
                empresa=self.empresa_1,
                nombre='Pesca API',
                slug='pesca-api',
                tipo_servicio='pesca',
            )
            self.servicio_2 = Servicio.objects.create(
                empresa=self.empresa_2,
                nombre='Transporte API',
                slug='transporte-api',
                tipo_servicio='transporte',
            )
            self.tarifa_transporte = TransporteTarifa.objects.create(
                empresa=self.empresa_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1,
                personas_max=4,
                precio=Decimal('2000.00'),
                precio_usd=Decimal('120.00'),
                activo=True,
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                nombre='Paquete API',
                slug='paquete-api',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_1, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_2, orden=2)

        self.checkout_id = uuid.uuid4()
        with scope.con_empresa(self.empresa_1):
            self.orden = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                paquete=self.paquete,
                checkout_id=self.checkout_id,
                nombre_cliente='Cliente API',
                telefono_cliente='1234567890',
                correo_cliente='api@example.com',
                moneda='MXN',
                estado=Orden.Estado.ARMANDO,
            )
            self.reserva_1 = Reserva.objects.create(
                empresa=self.empresa_1,
                servicio=self.servicio_1,
                paquete=self.paquete,
                orden=self.orden,
                fecha=date(2026, 10, 15),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente API',
                telefono_cliente='1234567890',
                correo_cliente='api@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2 = Reserva.objects.create(
                empresa=self.empresa_2,
                servicio=self.servicio_2,
                paquete=None,
                orden=self.orden,
                fecha=date(2026, 10, 15),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente API',
                telefono_cliente='1234567890',
                correo_cliente='api@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
            )
            DetalleTransporte.objects.create(
                reserva=self.reserva_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                direccion_personalizada='Hotel Marina',
                fecha_regreso=date(2026, 10, 17),
            )

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_crear_pago_orden_flujo_exitoso(self, mock_configurar_stripe):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        intent_1 = mock.Mock(id='pi_api_1', client_secret='sec_1', status='requires_capture')
        intent_2 = mock.Mock(id='pi_api_2', client_secret='sec_2', status='requires_capture')
        cliente_1.payment_intents.create.return_value = intent_1
        cliente_2.payment_intents.create.return_value = intent_2

        url = f'/api/{self.sede.slug}/ordenes/{self.orden.id}/crear-pago/'
        res = self.client.post(url, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        pagos = res.json()
        self.assertEqual(len(pagos), 2)
        # Líder absorbe residuo (5000 - 2000 = 3000)
        pago_lider = next(p for p in pagos if p['empresa_slug'] == self.empresa_1.slug)
        self.assertEqual(pago_lider['monto'], '3000.00')
        self.assertEqual(pago_lider['client_secret'], 'sec_1')

        # Transporte toma su tarifa (2000)
        pago_trans = next(p for p in pagos if p['empresa_slug'] == self.empresa_2.slug)
        self.assertEqual(pago_trans['monto'], '2000.00')
        self.assertEqual(pago_trans['client_secret'], 'sec_2')

        with scope.con_empresa(self.empresa_1):
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.AUTORIZANDO)

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_flujo_exitoso(self, mock_configurar_stripe):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_api_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_api_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        intent_1 = mock.Mock(id='pi_api_1', status='requires_capture')
        intent_2 = mock.Mock(id='pi_api_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.AUTORIZANDO
            self.orden.save(update_fields=['estado'])

        url = f'/api/{self.sede.slug}/ordenes/{self.orden.id}/confirmar-captura/'
        res = self.client.post(url, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['estado'], 'autorizada')

        cliente_1.payment_intents.capture.assert_called_once_with(
            'pi_api_1', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_1.id}-capture'},
        )
        cliente_2.payment_intents.capture.assert_called_once_with(
            'pi_api_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-capture'},
        )

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_confirmar_captura_flujo_fallo_revierte(self, mock_configurar_stripe):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_api_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_api_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        # Un intent no completó autorización
        intent_1 = mock.Mock(id='pi_api_1', status='requires_confirmation')
        intent_2 = mock.Mock(id='pi_api_2', status='requires_capture')
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        url = f'/api/{self.sede.slug}/ordenes/{self.orden.id}/confirmar-captura/'
        res = self.client.post(url, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['estado'], 'cancelada')
        self.assertIn('motivo', res.json())
        self.assertIn('retención', res.json()['motivo'])
        self.assertNotIn('autorización', res.json()['motivo'])

        cliente_2.payment_intents.cancel.assert_called_once_with(
            'pi_api_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-cancel'},
        )

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_get_orden_reanudar(self, mock_configurar_stripe):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_stripe.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.stripe_payment_intent_id = 'pi_api_1'
            self.reserva_1.save(update_fields=['stripe_payment_intent_id'])
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.stripe_payment_intent_id = 'pi_api_2'
            self.reserva_2.save(update_fields=['stripe_payment_intent_id'])

        # 1er pago ya autorizado (requires_capture), 2do pago pendiente (requires_payment_method)
        intent_1 = mock.Mock(id='pi_api_1', status='requires_capture', client_secret='sec_1', amount=300000)
        intent_2 = mock.Mock(id='pi_api_2', status='requires_payment_method', client_secret='sec_2', amount=200000)
        cliente_1.payment_intents.retrieve.return_value = intent_1
        cliente_2.payment_intents.retrieve.return_value = intent_2

        # Vía ID
        url_id = f'/api/{self.sede.slug}/ordenes/{self.orden.id}/'
        res = self.client.get(url_id)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['id'], self.orden.id)
        self.assertEqual(len(data['reservas']), 2)
        r1 = next(r for r in data['reservas'] if r['empresa_slug'] == self.empresa_1.slug)
        self.assertEqual(r1['pago']['estado_pi'], 'requires_capture')
        r2 = next(r for r in data['reservas'] if r['empresa_slug'] == self.empresa_2.slug)
        self.assertEqual(r2['pago']['estado_pi'], 'requires_payment_method')

        # Vía checkout_id
        url_cid = f'/api/{self.sede.slug}/ordenes/?checkout_id={self.checkout_id}'
        res_cid = self.client.get(url_cid)
        self.assertEqual(res_cid.status_code, 200)
        self.assertEqual(res_cid.json()['id'], self.orden.id)

    def test_crear_pago_orden_capturada_409(self):
        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.CAPTURADA
            self.orden.save(update_fields=['estado'])

        url = f'/api/{self.sede.slug}/ordenes/{self.orden.id}/crear-pago/'
        res = self.client.post(url, content_type='application/json')
        self.assertEqual(res.status_code, 409)


# postgres-only
@skipUnless(connection.vendor == 'postgresql', 'Requiere PostgreSQL y RLS')
class WebhookOrdenTest(TransactionTestCase):
    def setUp(self):
        from apps.fleet.enums import TipoTraslado
        from apps.bookings.models import DetalleTransporte

        self.sede = Sede.objects.create(
            nombre='Sede Webhook Orden', slug='sede-webhook-orden', zona_horaria='America/Mazatlan',
        )
        self.empresa_1 = Empresa.objects.create(
            nombre='Empresa Pesca Webhook',
            slug='emp-wh-pesca',
            sede=self.sede,
            stripe_secret_key='sk_test_wh_1',
            stripe_webhook_secret='whsec_wh_1',
            stripe_publishable_key='pk_test_wh_1',
        )
        self.empresa_2 = Empresa.objects.create(
            nombre='Empresa Transporte Webhook',
            slug='emp-wh-transporte',
            sede=self.sede,
            stripe_secret_key='sk_test_wh_2',
            stripe_webhook_secret='whsec_wh_2',
            stripe_publishable_key='pk_test_wh_2',
        )
        with scope.como_operador_plataforma():
            self.servicio_1 = Servicio.objects.create(
                empresa=self.empresa_1,
                nombre='Pesca Webhook',
                slug='pesca-webhook',
                tipo_servicio='pesca',
                estrategia_cupo='bajo_demanda',
            )
            self.servicio_2 = Servicio.objects.create(
                empresa=self.empresa_2,
                nombre='Transporte Webhook',
                slug='transporte-webhook',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                nombre='Paquete Webhook',
                slug='paquete-webhook',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_1, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_2, orden=2)

        with scope.con_empresa(self.empresa_1):
            self.orden = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                paquete=self.paquete,
                nombre_cliente='Cliente Webhook',
                telefono_cliente='1234567890',
                correo_cliente='webhook@example.com',
                moneda='MXN',
                estado=Orden.Estado.AUTORIZADA,
            )
            self.reserva_1 = Reserva.objects.create(
                empresa=self.empresa_1,
                servicio=self.servicio_1,
                paquete=self.paquete,
                orden=self.orden,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Webhook',
                telefono_cliente='1234567890',
                correo_cliente='webhook@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_wh_1',
                precio_total=Decimal('3000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2 = Reserva.objects.create(
                empresa=self.empresa_2,
                servicio=self.servicio_2,
                paquete=None,
                orden=self.orden,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Webhook',
                telefono_cliente='1234567890',
                correo_cliente='webhook@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_wh_2',
                precio_total=Decimal('2000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
            DetalleTransporte.objects.create(
                reserva=self.reserva_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                direccion_personalizada='Hotel Webhook',
                fecha_regreso=date(2026, 11, 22),
            )

    @mock.patch('apps.payments.services.notificar_orden_pagada')
    def test_dos_webhooks_cierran_orden_y_tercero_no_renotifica(self, mock_notificar):
        intent_1 = {
            'id': 'pi_wh_1',
            'amount_received': 300000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_1.id)},
        }
        intent_2 = {
            'id': 'pi_wh_2',
            'amount_received': 200000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_2.id)},
        }

        # 1. Primer webhook bajo RLS de empresa_1
        with scope.con_empresa(self.empresa_1):
            res_1 = aplicar_pago_exitoso(intent_1, self.empresa_1)
            self.assertEqual(res_1, APLICADO)
            self.reserva_1.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.PAGADA)
            self.orden.refresh_from_db()
            # No se cierra la orden aún ni se notifica
            self.assertEqual(self.orden.estado, Orden.Estado.AUTORIZADA)
            self.assertIsNone(self.orden.notificada_en)
            mock_notificar.assert_not_called()

        # 2. Segundo webhook bajo RLS de empresa_2
        with scope.con_empresa(self.empresa_2):
            res_2 = aplicar_pago_exitoso(intent_2, self.empresa_2)
            self.assertEqual(res_2, APLICADO)
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.PAGADA)
            self.orden.refresh_from_db()
            # Ahora la orden debe estar capturada y con notificada_en sellado
            self.assertEqual(self.orden.estado, Orden.Estado.CAPTURADA)
            self.assertIsNotNone(self.orden.notificada_en)
            mock_notificar.assert_called_once_with(self.orden)

        # 3. Tercer webhook duplicado (reintento de Stripe) bajo RLS de empresa_2
        with scope.con_empresa(self.empresa_2):
            res_3 = aplicar_pago_exitoso(intent_2, self.empresa_2)
            self.assertEqual(res_3, 'ya_aplicado')

        # No re-notifica ni altera notificada_en
        mock_notificar.assert_called_once()


class CompensacionOrdenTest(TransactionTestCase):
    def setUp(self):
        from apps.fleet.enums import TipoTraslado
        from apps.bookings.models import DetalleTransporte

        self.sede = Sede.objects.create(
            nombre='Sede Comp Orden', slug='sede-comp-orden', zona_horaria='America/Mazatlan',
        )
        self.empresa_1 = Empresa.objects.create(
            nombre='Empresa Pesca Comp',
            slug='emp-comp-pesca',
            sede=self.sede,
            stripe_secret_key='sk_test_comp_1',
            stripe_webhook_secret='whsec_comp_1',
            stripe_publishable_key='pk_test_comp_1',
        )
        self.empresa_2 = Empresa.objects.create(
            nombre='Empresa Transporte Comp',
            slug='emp-comp-transporte',
            sede=self.sede,
            stripe_secret_key='sk_test_comp_2',
            stripe_webhook_secret='whsec_comp_2',
            stripe_publishable_key='pk_test_comp_2',
        )
        with scope.como_operador_plataforma():
            # Pesca sin recursos: forzará SinCupoError en Caso D
            self.servicio_1 = Servicio.objects.create(
                empresa=self.empresa_1,
                nombre='Pesca Comp',
                slug='pesca-comp',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
            )
            self.servicio_2 = Servicio.objects.create(
                empresa=self.empresa_2,
                nombre='Transporte Comp',
                slug='transporte-comp',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                nombre='Paquete Comp',
                slug='paquete-comp',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_1, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_2, orden=2)

        with scope.con_empresa(self.empresa_1):
            self.orden = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                paquete=self.paquete,
                nombre_cliente='Cliente Comp',
                telefono_cliente='1234567890',
                correo_cliente='comp@example.com',
                moneda='MXN',
                estado=Orden.Estado.AUTORIZADA,
            )
            self.reserva_1 = Reserva.objects.create(
                empresa=self.empresa_1,
                servicio=self.servicio_1,
                paquete=self.paquete,
                orden=self.orden,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Comp',
                telefono_cliente='1234567890',
                correo_cliente='comp@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_comp_1',
                precio_total=Decimal('3000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2 = Reserva.objects.create(
                empresa=self.empresa_2,
                servicio=self.servicio_2,
                paquete=None,
                orden=self.orden,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Comp',
                telefono_cliente='1234567890',
                correo_cliente='comp@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_comp_2',
                precio_total=Decimal('2000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
            DetalleTransporte.objects.create(
                reserva=self.reserva_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                direccion_personalizada='Hotel Comp',
                fecha_regreso=date(2026, 11, 22),
            )

    @mock.patch('apps.payments.services.configurar_stripe')
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_compensacion_orden_cuando_falla_cupo(self, mock_stripe_ordenes, mock_stripe_services):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()

        def resolver_cliente(emp):
            return cliente_1 if emp.id == self.empresa_1.id else cliente_2

        mock_stripe_services.side_effect = resolver_cliente
        mock_stripe_ordenes.side_effect = resolver_cliente

        intent_1_obj = mock.Mock(id='pi_comp_1', status='succeeded', amount=300000)
        intent_2_obj = mock.Mock(id='pi_comp_2', status='succeeded', amount=200000)
        cliente_1.payment_intents.retrieve.return_value = intent_1_obj
        cliente_2.payment_intents.retrieve.return_value = intent_2_obj

        # La compensación completa debe usar exclusivamente ordenes.revertir_orden.
        def refund_1(params, options=None):
            intent_1_obj.status = 'refunded'
            return mock.Mock()

        def refund_2(params, options=None):
            intent_2_obj.status = 'refunded'
            return mock.Mock()

        cliente_1.refunds.create.side_effect = refund_1
        cliente_2.refunds.create.side_effect = refund_2

        intent_data_1 = {
            'id': 'pi_comp_1',
            'amount_received': 300000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_1.id)},
        }

        with scope.con_empresa(self.empresa_1):
            res = aplicar_pago_exitoso(intent_data_1, self.empresa_1)
            self.assertEqual(res, SIN_CUPO_REEMBOLSADO)

        # 1. Ambas reservas quedan canceladas y reembolsadas
        with scope.con_empresa(self.empresa_1):
            self.reserva_1.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.CANCELADA)
            self.assertTrue(self.reserva_1.reembolsada)
            self.assertIn('sin cupo', self.reserva_1.motivo_cancelacion.lower())

        with scope.con_empresa(self.empresa_2):
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.CANCELADA)
            self.assertTrue(self.reserva_2.reembolsada)

        # 2. La orden queda cancelada
        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

        # 3. Refund de ambas en Stripe
        mock_stripe_services.assert_not_called()
        cliente_1.refunds.create.assert_called_once_with(
            {'payment_intent': 'pi_comp_1'},
            {'idempotency_key': f'orden-{self.orden.id}-{self.empresa_1.id}-refund'},
        )
        cliente_2.refunds.create.assert_called_once_with(
            {'payment_intent': 'pi_comp_2'},
            {'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-refund'},
        )

        # 4. Idempotencia: llamar revertir_orden de nuevo no re-reembolsa
        from apps.payments.ordenes import revertir_orden
        revertir_orden(self.orden, 'segunda llamada')
        cliente_1.refunds.create.assert_called_once()
        cliente_2.refunds.create.assert_called_once()


class ConciliarOrdenesTest(TransactionTestCase):
    def setUp(self):
        from apps.fleet.enums import TipoTraslado
        from apps.bookings.models import DetalleTransporte

        self.sede = Sede.objects.create(
            nombre='Sede Conciliar', slug='sede-conciliar', zona_horaria='America/Mazatlan',
        )
        self.empresa_1 = Empresa.objects.create(
            nombre='Empresa Pesca Conciliar',
            slug='emp-conc-pesca',
            sede=self.sede,
            stripe_secret_key='sk_test_conc_1',
            stripe_webhook_secret='whsec_conc_1',
            stripe_publishable_key='pk_test_conc_1',
        )
        self.empresa_2 = Empresa.objects.create(
            nombre='Empresa Transporte Conciliar',
            slug='emp-conc-transporte',
            sede=self.sede,
            stripe_secret_key='sk_test_conc_2',
            stripe_webhook_secret='whsec_conc_2',
            stripe_publishable_key='pk_test_conc_2',
        )
        with scope.como_operador_plataforma():
            self.servicio_1 = Servicio.objects.create(
                empresa=self.empresa_1,
                nombre='Pesca Conciliar',
                slug='pesca-conciliar',
                tipo_servicio='pesca',
                estrategia_cupo='bajo_demanda',
            )
            self.servicio_2 = Servicio.objects.create(
                empresa=self.empresa_2,
                nombre='Transporte Conciliar',
                slug='transporte-conciliar',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                nombre='Paquete Conciliar',
                slug='paquete-conciliar',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_1, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_2, orden=2)

        with scope.con_empresa(self.empresa_1):
            self.orden = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                paquete=self.paquete,
                nombre_cliente='Cliente Conciliar',
                telefono_cliente='1234567890',
                correo_cliente='conciliar@example.com',
                moneda='MXN',
                estado=Orden.Estado.AUTORIZANDO,
            )
            self.reserva_1 = Reserva.objects.create(
                empresa=self.empresa_1,
                servicio=self.servicio_1,
                paquete=self.paquete,
                orden=self.orden,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Conciliar',
                telefono_cliente='1234567890',
                correo_cliente='conciliar@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_conc_1',
                precio_total=Decimal('3000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2 = Reserva.objects.create(
                empresa=self.empresa_2,
                servicio=self.servicio_2,
                paquete=None,
                orden=self.orden,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Conciliar',
                telefono_cliente='1234567890',
                correo_cliente='conciliar@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_conc_2',
                precio_total=Decimal('2000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
            DetalleTransporte.objects.create(
                reserva=self.reserva_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                direccion_personalizada='Hotel Conciliar',
                fecha_regreso=date(2026, 11, 22),
            )

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_webhook_perdido_ambas_empresas_aplica_y_captura_orden(self, mock_configurar):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        intent_1_dict = {
            'id': 'pi_conc_1',
            'status': 'succeeded',
            'amount_received': 300000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_1.id)},
        }
        intent_1_mock = mock.MagicMock(id='pi_conc_1', status='succeeded', amount_received=300000, currency='mxn')
        intent_1_mock.__getitem__.side_effect = lambda k: intent_1_dict[k]
        cliente_1.payment_intents.retrieve.return_value = intent_1_mock

        intent_2_dict = {
            'id': 'pi_conc_2',
            'status': 'succeeded',
            'amount_received': 200000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_2.id)},
        }
        intent_2_mock = mock.MagicMock(id='pi_conc_2', status='succeeded', amount_received=200000, currency='mxn')
        intent_2_mock.__getitem__.side_effect = lambda k: intent_2_dict[k]
        cliente_2.payment_intents.retrieve.return_value = intent_2_mock

        call_command('conciliar_pagos')

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.PAGADA)
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.PAGADA)
        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CAPTURADA)

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_una_succeeded_otra_requires_confirmation_con_timeout_revierte_orden(
        self, mock_configurar_conciliar, mock_configurar_ordenes,
    ):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar_conciliar.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2
        mock_configurar_ordenes.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        intent_1_mock = mock.Mock(id='pi_conc_1', status='succeeded', amount=300000)
        cliente_1.payment_intents.retrieve.return_value = intent_1_mock

        intent_2_mock = mock.Mock(id='pi_conc_2', status='requires_confirmation', amount=200000)
        cliente_2.payment_intents.retrieve.return_value = intent_2_mock

        # Simulamos que pasaron más de 24 horas
        hace_25h = timezone.now() - timedelta(hours=25)
        with scope.como_operador_plataforma():
            Orden.objects.filter(pk=self.orden.pk).update(actualizado_en=hace_25h)

        call_command('conciliar_pagos')

        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

        with scope.con_empresa(self.empresa_1):
            self.reserva_1.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.CANCELADA)
            self.assertTrue(self.reserva_1.reembolsada)

        with scope.con_empresa(self.empresa_2):
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.CANCELADA)

        cliente_1.refunds.create.assert_called_once()
        cliente_2.payment_intents.cancel.assert_called_once_with(
            'pi_conc_2', options={'idempotency_key': f'orden-{self.orden.id}-{self.empresa_2.id}-cancel'},
        )

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_conciliar_dos_veces_seguidas_es_idempotente(self, mock_configurar):
        cliente_1 = mock.Mock()
        cliente_2 = mock.Mock()
        mock_configurar.side_effect = lambda emp: cliente_1 if emp.id == self.empresa_1.id else cliente_2

        intent_1_dict = {
            'id': 'pi_conc_1',
            'status': 'succeeded',
            'amount_received': 300000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_1.id)},
        }
        intent_1_mock = mock.MagicMock(id='pi_conc_1', status='succeeded', amount_received=300000, currency='mxn')
        intent_1_mock.__getitem__.side_effect = lambda k: intent_1_dict[k]
        cliente_1.payment_intents.retrieve.return_value = intent_1_mock

        intent_2_dict = {
            'id': 'pi_conc_2',
            'status': 'succeeded',
            'amount_received': 200000,
            'currency': 'mxn',
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(self.reserva_2.id)},
        }
        intent_2_mock = mock.MagicMock(id='pi_conc_2', status='succeeded', amount_received=200000, currency='mxn')
        intent_2_mock.__getitem__.side_effect = lambda k: intent_2_dict[k]
        cliente_2.payment_intents.retrieve.return_value = intent_2_mock

        # Primera corrida
        call_command('conciliar_pagos')

        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CAPTURADA)

        # Segunda corrida
        call_command('conciliar_pagos')

        with scope.como_operador_plataforma():
            self.orden.refresh_from_db()
            self.assertEqual(self.orden.estado, Orden.Estado.CAPTURADA)
        with scope.con_empresa(self.empresa_1):
            self.reserva_1.refresh_from_db()
            self.assertEqual(self.reserva_1.estado, Reserva.Estado.PAGADA)
        with scope.con_empresa(self.empresa_2):
            self.reserva_2.refresh_from_db()
            self.assertEqual(self.reserva_2.estado, Reserva.Estado.PAGADA)


class RevisarOrdenesTest(TransactionTestCase):
    def setUp(self):
        from apps.fleet.enums import TipoTraslado
        from apps.bookings.models import DetalleTransporte

        self.sede = Sede.objects.create(
            nombre='Sede Revisar', slug='sede-revisar', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            nombre='Empresa Revisar',
            slug='emp-revisar',
            sede=self.sede,
            stripe_secret_key='sk_test_revisar',
            stripe_webhook_secret='whsec_revisar',
            stripe_publishable_key='pk_test_revisar',
        )
        with scope.como_operador_plataforma():
            self.servicio = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Pesca Revisar',
                slug='pesca-revisar',
                tipo_servicio='pesca',
                estrategia_cupo='bajo_demanda',
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa,
                nombre='Paquete Revisar',
                slug='paquete-revisar',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio, orden=1)

        with scope.con_empresa(self.empresa):
            # Orden 1: Atascada (hace 3 horas, estado AUTORIZANDO)
            self.orden_atascada = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa,
                paquete=self.paquete,
                nombre_cliente='Cliente Atascado',
                telefono_cliente='1234567890',
                correo_cliente='atascado@example.com',
                moneda='MXN',
                estado=Orden.Estado.AUTORIZANDO,
            )
            hace_3h = timezone.now() - timedelta(hours=3)
            Orden.objects.filter(pk=self.orden_atascada.pk).update(actualizado_en=hace_3h)

            self.reserva_atascada = Reserva.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                paquete=self.paquete,
                orden=self.orden_atascada,
                fecha=date(2026, 11, 20),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Atascado',
                telefono_cliente='1234567890',
                correo_cliente='atascado@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PENDIENTE_PAGO,
                stripe_payment_intent_id='pi_atascado',
                precio_total=Decimal('5000.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )

            # Orden 2: Capturada (hace 3 horas, pero ya pagada)
            self.orden_capturada = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa,
                paquete=self.paquete,
                nombre_cliente='Cliente Capturado',
                telefono_cliente='1234567890',
                correo_cliente='capturado@example.com',
                moneda='MXN',
                estado=Orden.Estado.CAPTURADA,
            )
            Orden.objects.filter(pk=self.orden_capturada.pk).update(actualizado_en=hace_3h)

            # Orden 3: Reciente (hace 10 minutos, estado AUTORIZANDO)
            self.orden_reciente = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa,
                paquete=self.paquete,
                nombre_cliente='Cliente Reciente',
                telefono_cliente='1234567890',
                correo_cliente='reciente@example.com',
                moneda='MXN',
                estado=Orden.Estado.AUTORIZANDO,
            )

    @mock.patch('apps.payments.management.commands.revisar_ordenes.configurar_stripe')
    def test_revisar_ordenes_lista_atascada_y_no_capturada_ni_reciente(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente
        cliente.payment_intents.retrieve.return_value = mock.Mock(status='requires_action')

        salida = StringIO()
        call_command('revisar_ordenes', stdout=salida)
        texto = salida.getvalue()

        self.assertIn(f'Orden #{self.orden_atascada.pk}', texto)
        self.assertIn('Cliente Atascado', texto)
        self.assertIn('requires_action', texto)

        self.assertNotIn(f'Orden #{self.orden_capturada.pk}', texto)
        self.assertNotIn('Cliente Capturado', texto)

        self.assertNotIn(f'Orden #{self.orden_reciente.pk}', texto)
        self.assertNotIn('Cliente Reciente', texto)

        # Verificar que nada fue alterado en la base de datos
        with scope.como_operador_plataforma():
            self.orden_atascada.refresh_from_db()
            self.assertEqual(self.orden_atascada.estado, Orden.Estado.AUTORIZANDO)
        with scope.con_empresa(self.empresa):
            self.reserva_atascada.refresh_from_db()
            self.assertEqual(self.reserva_atascada.estado, Reserva.Estado.PENDIENTE_PAGO)

    @mock.patch('apps.payments.management.commands.revisar_ordenes.configurar_stripe')
    def test_revisar_ordenes_con_flag_horas_filtra_correctamente(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente

        salida = StringIO()
        # Si filtramos con --horas 4, la orden de 3 horas no debe salir
        call_command('revisar_ordenes', '--horas', '4', stdout=salida)
        texto = salida.getvalue()

        self.assertIn('No se encontraron órdenes atascadas (> 4h)', texto)
        self.assertNotIn(f'Orden #{self.orden_atascada.pk}', texto)




