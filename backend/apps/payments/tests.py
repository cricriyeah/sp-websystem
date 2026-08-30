"""Pruebas del cobro. Lo que se protege aqui es que nadie pague dos veces y que
lo cobrado cuadre con lo calculado — Stripe va simulado, no se llama a la red.
"""
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

import stripe
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.bookings.models import CUPO_MAXIMO_DEFAULT, Reserva, ReservaExtra, ReservaTransporte
from apps.fleet.models import CodigoPromocional, ExtrasItem, Tarifa, TransportePrecio
from apps.testing import ApiTestCase, crear_flota

from .checks import revisar_llaves_de_stripe
from .pricing import (
    PERSONAS_INCLUIDAS,
    a_centavos,
    cargo_por_extra,
    cargo_por_personas,
    cargo_por_transporte,
    de_centavos,
    monto_inicial,
    personas_extra,
)

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}


class LlavesDeStripeCruzadasTests(TestCase):
    """Check de arranque que detecta una llave de Stripe puesta en la variable
    equivocada.

    Nace de un caso real en produccion: en Render quedo el signing secret del
    webhook (`whsec_...`) dentro de `STRIPE_SECRET_KEY`. Stripe rechazaba cada
    llamada con `AuthenticationError`, `crear-pago` devolvia 502 y el checkout
    mostraba un error generico — el sintoma no apuntaba a la causa por ningun
    lado. Las dos llaves tienen prefijo fijo, asi que el cruce se puede ver sin
    hablar con Stripe.
    """

    def errores(self, **llaves):
        with override_settings(**llaves):
            return [e.id for e in revisar_llaves_de_stripe(None)]

    def test_llaves_correctas_no_reportan_nada(self):
        self.assertEqual(self.errores(**LLAVES), [])

    def test_llaves_vacias_no_reportan_nada(self):
        # Vacio significa "esta funcion esta apagada", que es comportamiento
        # documentado: sin llaves, crear-pago responde 503 a proposito.
        self.assertEqual(self.errores(STRIPE_SECRET_KEY='', STRIPE_WEBHOOK_SECRET=''), [])

    def test_el_signing_secret_dentro_de_la_llave_secreta(self):
        """El caso que de verdad paso."""
        self.assertEqual(
            self.errores(STRIPE_SECRET_KEY='whsec_falsa', STRIPE_WEBHOOK_SECRET='whsec_falsa'),
            ['payments.E001'],
        )

    def test_la_llave_secreta_dentro_del_signing_secret(self):
        self.assertEqual(
            self.errores(STRIPE_SECRET_KEY='sk_test_falsa', STRIPE_WEBHOOK_SECRET='sk_test_falsa'),
            ['payments.E002'],
        )

    def test_las_dos_cruzadas_reportan_las_dos(self):
        self.assertEqual(
            self.errores(STRIPE_SECRET_KEY='whsec_falsa', STRIPE_WEBHOOK_SECRET='sk_test_falsa'),
            ['payments.E001', 'payments.E002'],
        )

    def test_la_publicable_en_lugar_de_la_secreta(self):
        # Otro cruce plausible: las dos salen de la misma pantalla del dashboard.
        self.assertEqual(self.errores(STRIPE_SECRET_KEY='pk_test_falsa'), ['payments.E001'])

    def test_el_mensaje_no_incluye_el_valor_de_la_llave(self):
        """Un check que imprime la llave la deja en el log del deploy."""
        with override_settings(STRIPE_SECRET_KEY='whsec_secretisimo'):
            texto = ' '.join(f'{e.msg} {e.hint}' for e in revisar_llaves_de_stripe(None))
        self.assertNotIn('secretisimo', texto)


CHECKOUT_ID = '11111111-1111-4111-8111-111111111111'


def crear_reserva(**overrides):
    crear_flota()  # el motor de cupo le pregunta a la flota; sin pangas no cabe nadie
    datos = {
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
        self.assertEqual(cargo_por_extra(Decimal('150'), True, 1), Decimal('150'))
        self.assertEqual(cargo_por_extra(Decimal('150'), True, 4), Decimal('600'))

    def test_extra_plano_no_multiplica_por_personas(self):
        self.assertEqual(cargo_por_extra(Decimal('400'), False, 5), Decimal('400'))

    def test_extra_sin_precio_en_la_moneda_es_none(self):
        self.assertIsNone(cargo_por_extra(None, True, 3))

    def test_transporte_sin_recargo_bajo_el_minimo(self):
        self.assertEqual(
            cargo_por_transporte(Decimal('2000'), Decimal('1500'), 4, 3), Decimal('2000')
        )

    def test_transporte_con_recargo_desde_el_minimo(self):
        self.assertEqual(
            cargo_por_transporte(Decimal('2000'), Decimal('1500'), 4, 4), Decimal('3500')
        )

    def test_transporte_sin_precio_base_en_la_moneda_es_none(self):
        self.assertIsNone(cargo_por_transporte(None, Decimal('1500'), 4, 5))


@override_settings(**LLAVES)
class CrearPagoTests(ApiTestCase):
    def setUp(self):
        Tarifa.objects.create(
            precio=Decimal('4500.00'), precio_usd=Decimal('260.00'),
            precio_persona_extra=Decimal('500.00'), precio_persona_extra_usd=Decimal('30.00'),
        )
        self.reserva = crear_reserva()
        self.url = f'/api/reservas/{self.reserva.pk}/crear-pago/'

    def post(self, **body):
        datos = {'forma_pago': 'completo', 'checkout_id': str(self.reserva.checkout_id)}
        datos.update(body)
        return self.client.post(self.url, datos, content_type='application/json')

    def seleccionar_extra(self, reserva=None, cantidad_solicitada=None, **overrides):
        """Simula lo que deja el checkout: la SELECCION de un extra, sin precio
        congelado todavia (eso solo lo escribe `CrearPagoView`). `cantidad_solicitada`
        es de la seleccion (`ReservaExtra`), no del catalogo — se separa aparte."""
        datos = {
            'tipo': ExtrasItem.Tipo.BRUNCH, 'nombre': 'Brunch', 'precio': Decimal('300'),
            'precio_usd': Decimal('18'), 'cobrar_por_persona': True,
        }
        datos.update(overrides)
        item = ExtrasItem.objects.create(**datos)
        return ReservaExtra.objects.create(
            reserva=reserva or self.reserva, extras_item=item, cantidad_solicitada=cantidad_solicitada,
        )

    def seleccionar_transporte(self, reserva=None, zona=TransportePrecio.Zona.CENTRO, **precio_overrides):
        """Idem para transporte: crea el precio de zona vigente y deja la
        SELECCION (sin `numero_personas`/`precio_calculado`) en la reserva."""
        datos = {'zona': zona, 'precio_base': Decimal('2000'), 'recargo_grupo': Decimal('1500'),
                  'min_personas_recargo': 4}
        datos.update(precio_overrides)
        TransportePrecio.objects.create(**datos)
        return ReservaTransporte.objects.create(
            reserva=reserva or self.reserva, zona=zona, direccion_personalizada='Malecon 123',
        )

    @mock.patch('stripe.PaymentIntent.create')
    def test_cobra_lo_que_calcula_el_servidor_no_lo_que_manda_el_cliente(self, create):
        create.return_value = intent_falso()
        # El cliente intenta colar su propio total y sus propios extras.
        response = self.post(precio_total='1.00', total=1, lleva_lunch=True, amenities=['lunch'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs['amount'], a_centavos(Decimal('4500.00')))
        self.assertEqual(response.json()['monto_a_cobrar'], '4500.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_anticipo_cobra_el_30_por_ciento(self, create):
        create.return_value = intent_falso()
        response = self.post(forma_pago='anticipo')

        self.assertEqual(create.call_args.kwargs['amount'], 135000)
        self.assertEqual(response.json()['monto_a_cobrar'], '1350.00')
        # El total completo queda guardado: el 70% se cobra en efectivo.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.precio_total, Decimal('4500.00'))
        self.assertEqual(self.reserva.saldo_pendiente, Decimal('4500.00'))

    @mock.patch('stripe.PaymentIntent.create')
    def test_hasta_3_personas_el_precio_no_cambia(self, create):
        create.return_value = intent_falso()
        for personas in (1, 2, 3):
            # Se limpia el intent para que cada vuelta sea un checkout nuevo y no
            # entre por la rama que reusa el intent anterior.
            Reserva.objects.filter(pk=self.reserva.pk).update(
                numero_personas=personas, stripe_payment_intent_id=''
            )
            self.assertEqual(self.post().json()['monto_a_cobrar'], '4500.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_cobra_500_por_cada_persona_arriba_de_3(self, create):
        create.return_value = intent_falso()
        # 5 es el tope de la flota (MAX_PERSONAS): la panga mas grande lleva 5.
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        # 4500 del viaje + 2 personas extra x 500.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '5500.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_el_cargo_por_personas_sale_de_la_reserva_no_del_cliente(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        # Aunque el cliente insista en que van 2, se cobra por las 5 reservadas.
        self.assertEqual(self.post(numero_personas=2).json()['monto_a_cobrar'], '5500.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_el_anticipo_incluye_el_cargo_por_personas(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        # 30% de 5500.
        self.assertEqual(self.post(forma_pago='anticipo').json()['monto_a_cobrar'], '1650.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_el_brunch_se_cobra_por_cada_persona(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=4)
        self.seleccionar_extra()
        # 4500 del viaje + 1 persona extra x 500 + 4 brunches x 300.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '6200.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_cantidad_editable_cobra_solo_lo_que_el_cliente_pidio(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        self.seleccionar_extra(
            tipo=ExtrasItem.Tipo.LICENCIA, nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cantidad_editable=True, cantidad_solicitada=2,
        )
        # 4500 + 2 personas extra x 500 + 2 licencias x 450 (no 5).
        response = self.post()

        self.assertEqual(response.json()['monto_a_cobrar'], '6400.00')
        extra = ReservaExtra.objects.get(reserva=self.reserva)
        self.assertEqual(extra.cantidad, 2)

    @mock.patch('stripe.PaymentIntent.create')
    def test_cantidad_editable_se_acota_al_grupo_nunca_cobra_de_mas(self, create):
        create.return_value = intent_falso()
        # El cliente eligio "5" antes de bajar el grupo a 2: nunca debe cobrar
        # licencia para mas personas de las que trae la reserva.
        self.seleccionar_extra(
            tipo=ExtrasItem.Tipo.LICENCIA, nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cantidad_editable=True, cantidad_solicitada=5,
        )
        response = self.post()

        # 4500 + 2 licencias x 450 (acotado a numero_personas=2, no 5).
        self.assertEqual(response.json()['monto_a_cobrar'], '5400.00')
        extra = ReservaExtra.objects.get(reserva=self.reserva)
        self.assertEqual(extra.cantidad, 2)

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_cantidad_solicitada_cantidad_editable_cobra_todo_el_grupo(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=4)
        self.seleccionar_extra(
            tipo=ExtrasItem.Tipo.LICENCIA, nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cantidad_editable=True,
        )
        # Sin cantidad_solicitada (None): mismo comportamiento de siempre, todo el grupo.
        # 4500 + 1 persona extra x 500 + 4 licencias x 450.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '6800.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_transporte_sin_suficientes_personas_no_aplica_el_recargo(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        transporte = self.seleccionar_transporte()
        transporte.personas_solicitadas = 2
        transporte.save(update_fields=['personas_solicitadas'])

        response = self.post()

        # 4500 + 2 personas extra x 500 + 2000 de transporte SIN recargo (solo
        # 2 personas suben, aunque la reserva completa sea de 5).
        self.assertEqual(response.json()['monto_a_cobrar'], '7500.00')
        transporte.refresh_from_db()
        self.assertEqual(transporte.numero_personas, 2)

    @mock.patch('stripe.PaymentIntent.create')
    def test_transporte_con_suficientes_personas_solicitadas_si_aplica_el_recargo(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=5)
        transporte = self.seleccionar_transporte()
        transporte.personas_solicitadas = 4
        transporte.save(update_fields=['personas_solicitadas'])

        response = self.post()

        # 4500 + 2 personas extra x 500 + 2000 + 1500 de recargo (4 alcanza el minimo).
        self.assertEqual(response.json()['monto_a_cobrar'], '9000.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_personas_solicitadas_transporte_usa_todo_el_grupo(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(numero_personas=4)
        self.seleccionar_transporte()

        response = self.post()

        # Sin personas_solicitadas (None): mismo comportamiento de siempre, todo
        # el grupo cuenta para el recargo. 4500 + 1 x 500 + 2000 + 1500.
        self.assertEqual(response.json()['monto_a_cobrar'], '8500.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_bebidas_no_suma_pero_transporte_si(self, create):
        create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(pide_bebidas=True)
        self.seleccionar_transporte()  # 2 personas, bajo el minimo de recargo: solo precio_base.
        # Bebidas la cotiza el agente aparte, no cambia el cobro. Transporte si suma.
        self.assertEqual(self.post().json()['monto_a_cobrar'], '6500.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_precio_de_extra_en_dolares_no_se_cobra_a_medias(self, create):
        reserva = crear_reserva(moneda='USD')
        self.seleccionar_extra(reserva=reserva, precio=Decimal('300'), precio_usd=None)
        response = self.client.post(
            f'/api/reservas/{reserva.pk}/crear-pago/',
            {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)
        create.assert_not_called()

    @mock.patch('stripe.PaymentIntent.create')
    def test_congela_el_precio_vigente_del_catalogo_no_el_de_cuando_se_selecciono(self, create):
        create.return_value = intent_falso()
        seleccion = self.seleccionar_extra(precio=Decimal('300'), precio_usd=Decimal('18'))
        # El precio de lista cambia despues de que el cliente eligio, antes de pagar.
        seleccion.extras_item.precio = Decimal('500')
        seleccion.extras_item.save(update_fields=['precio'])

        response = self.post()

        # 4500 + 2 personas x 500 (el precio vigente, no los 300 de cuando eligio).
        self.assertEqual(response.json()['monto_a_cobrar'], '5500.00')
        seleccion.refresh_from_db()
        self.assertEqual(seleccion.precio_unitario, Decimal('500'))
        self.assertEqual(seleccion.cantidad, 2)

    @mock.patch('stripe.PaymentIntent.create')
    def test_un_extra_desactivado_se_cae_sin_bloquear_los_demas(self, create):
        create.return_value = intent_falso()
        activo = self.seleccionar_extra(
            tipo=ExtrasItem.Tipo.LICENCIA, nombre='Licencia', precio=Decimal('450'),
            precio_usd=Decimal('25'), cobrar_por_persona=False,
        )
        a_caer = self.seleccionar_extra(precio=Decimal('300'), precio_usd=Decimal('18'))
        a_caer.extras_item.activo = False
        a_caer.extras_item.save(update_fields=['activo'])

        response = self.post()

        self.assertEqual(response.status_code, 200)
        # Solo la licencia entra al cobro: 4500 + 450.
        self.assertEqual(response.json()['monto_a_cobrar'], '4950.00')
        self.assertFalse(ReservaExtra.objects.filter(pk=a_caer.pk).exists())
        activo.refresh_from_db()
        self.assertEqual(activo.precio_unitario, Decimal('450'))

    @mock.patch('stripe.PaymentIntent.retrieve')
    @mock.patch('stripe.PaymentIntent.create')
    def test_409_por_pago_en_curso_no_deja_extras_a_medias(self, create, retrieve):
        create.return_value = intent_falso()
        self.post()

        extra = self.seleccionar_extra(precio=Decimal('300'), precio_usd=Decimal('18'))
        retrieve.return_value = intent_falso(status='processing')

        response = self.post()

        self.assertEqual(response.status_code, 409)
        extra.refresh_from_db()
        self.assertIsNone(extra.precio_unitario)
        self.assertIsNone(extra.cantidad)

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_cargo_en_dolares_no_se_cobra_a_medias(self, create):
        Tarifa.objects.create(
            precio=Decimal('4500.00'), precio_usd=Decimal('260.00'),
            precio_persona_extra=Decimal('500.00'), precio_persona_extra_usd=None,
        )
        reserva = crear_reserva(moneda='USD', numero_personas=5)
        response = self.client.post(
            f'/api/reservas/{reserva.pk}/crear-pago/',
            {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)
        create.assert_not_called()

    @mock.patch('stripe.PaymentIntent.create')
    def test_manda_idempotency_key(self, create):
        create.return_value = intent_falso()
        self.post()
        self.assertIn('idempotency_key', create.call_args.kwargs)

    @mock.patch('stripe.PaymentIntent.retrieve')
    @mock.patch('stripe.PaymentIntent.create')
    def test_dos_clics_reusan_el_mismo_intent(self, create, retrieve):
        create.return_value = intent_falso()
        self.post()

        retrieve.return_value = intent_falso()
        response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_count, 1)  # no se creo un segundo intent

    @mock.patch('stripe.PaymentIntent.modify')
    @mock.patch('stripe.PaymentIntent.retrieve')
    @mock.patch('stripe.PaymentIntent.create')
    def test_cambiar_los_extras_ajusta_el_intent_en_vez_de_duplicarlo(self, create, retrieve, modify):
        create.return_value = intent_falso()
        self.post()

        # El cliente vuelve atras y agrega el brunch: mismo intent, otro monto.
        self.seleccionar_extra(precio=Decimal('150'), precio_usd=Decimal('9'))
        retrieve.return_value = intent_falso()
        modify.return_value = intent_falso(amount=480000)
        self.post()

        self.assertEqual(create.call_count, 1)
        self.assertEqual(modify.call_args.kwargs['amount'], a_centavos(Decimal('4800.00')))

    @mock.patch('stripe.PaymentIntent.retrieve')
    @mock.patch('stripe.PaymentIntent.create')
    def test_no_crea_otro_intent_si_ya_hay_uno_cobrando(self, create, retrieve):
        create.return_value = intent_falso()
        self.post()

        retrieve.return_value = intent_falso(status='succeeded')
        response = self.post()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(create.call_count, 1)

    def test_reserva_ya_pagada_no_se_vuelve_a_cobrar(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save()
        self.assertEqual(self.post().status_code, 409)

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_precio_en_dolares_responde_503(self, create):
        Tarifa.objects.create(precio=Decimal('4500.00'), precio_usd=None)
        reserva = crear_reserva(moneda='USD')
        response = self.client.post(
            f'/api/reservas/{reserva.pk}/crear-pago/',
            {'amenities': [], 'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)
        create.assert_not_called()

    def test_forma_pago_invalida_responde_400(self):
        self.assertEqual(self.post(forma_pago='trueque').status_code, 400)

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_el_checkout_id_correcto_no_se_puede_cobrar(self, create):
        """Los ids de reserva son consecutivos y la API es publica: adivinar uno
        no debe alcanzar para generar cobros sobre la reserva de otra persona."""
        self.assertEqual(self.post(checkout_id=None).status_code, 403)
        self.assertEqual(self.post(checkout_id='22222222-2222-4222-8222-222222222222').status_code, 403)
        create.assert_not_called()

        create.return_value = intent_falso()
        self.assertEqual(self.post(checkout_id=str(self.reserva.checkout_id)).status_code, 200)

    @mock.patch('stripe.PaymentIntent.create')
    def test_una_reserva_de_whatsapp_no_se_cobra_por_esta_ruta(self, create):
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
        create.assert_not_called()

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

    @mock.patch('stripe.PaymentIntent.create')
    def test_codigo_promocional_valido_aplica_el_descuento(self, create):
        create.return_value = intent_falso()
        CodigoPromocional.objects.create(codigo='VERANO10', porcentaje_descuento=Decimal('10'))

        response = self.post(codigo_promocional='VERANO10')

        # 4500 - 10% = 4050.
        self.assertEqual(response.json()['monto_a_cobrar'], '4050.00')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.codigo_promocional.codigo, 'VERANO10')
        self.assertEqual(self.reserva.descuento_aplicado, Decimal('450.00'))
        self.assertEqual(self.reserva.precio_total, Decimal('4050.00'))

    @mock.patch('stripe.PaymentIntent.create')
    def test_codigo_promocional_no_distingue_mayusculas_ni_espacios(self, create):
        create.return_value = intent_falso()
        CodigoPromocional.objects.create(codigo='VERANO10', porcentaje_descuento=Decimal('10'))

        response = self.post(codigo_promocional=' verano10 ')

        self.assertEqual(response.json()['monto_a_cobrar'], '4050.00')

    @mock.patch('stripe.PaymentIntent.create')
    def test_codigo_promocional_inexistente_responde_400(self, create):
        response = self.post(codigo_promocional='NOEXISTE')

        self.assertEqual(response.status_code, 400)
        create.assert_not_called()
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.codigo_promocional)

    @mock.patch('stripe.PaymentIntent.create')
    def test_codigo_promocional_inactivo_responde_400(self, create):
        CodigoPromocional.objects.create(
            codigo='VIEJO', porcentaje_descuento=Decimal('10'), activo=False,
        )
        response = self.post(codigo_promocional='VIEJO')

        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    @mock.patch('stripe.PaymentIntent.create')
    def test_codigo_promocional_bajo_el_monto_minimo_responde_400(self, create):
        CodigoPromocional.objects.create(
            codigo='DESDE10000', porcentaje_descuento=Decimal('10'), monto_minimo=Decimal('10000'),
        )
        response = self.post(codigo_promocional='DESDE10000')

        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    @mock.patch('stripe.PaymentIntent.create')
    def test_sin_codigo_promocional_no_hay_descuento(self, create):
        create.return_value = intent_falso()
        self.post()

        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.codigo_promocional)
        self.assertIsNone(self.reserva.descuento_aplicado)

    @mock.patch('stripe.PaymentIntent.create')
    def test_el_descuento_se_calcula_sobre_el_subtotal_con_extras_y_transporte(self, create):
        create.return_value = intent_falso()
        CodigoPromocional.objects.create(codigo='VERANO10', porcentaje_descuento=Decimal('10'))
        self.seleccionar_extra()  # 2 personas x 300 = 600
        self.seleccionar_transporte()  # 2000, bajo el minimo de recargo

        # Subtotal: 4500 + 600 + 2000 = 7100. Descuento 10% = 710. Total 6390.
        response = self.post(codigo_promocional='VERANO10')

        self.assertEqual(response.json()['monto_a_cobrar'], '6390.00')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.descuento_aplicado, Decimal('710.00'))


class ValidarCodigoPromocionalTests(ApiTestCase):
    def get(self, **params):
        return self.client.get('/api/codigo-promocional/validar/', params)

    def test_codigo_valido(self):
        CodigoPromocional.objects.create(codigo='VERANO10', porcentaje_descuento=Decimal('10'))
        body = self.get(codigo='VERANO10', correo_cliente='ana@example.com').json()
        self.assertEqual(body, {'valido': True, 'porcentaje_descuento': '10.00'})

    def test_codigo_no_distingue_mayusculas_ni_espacios(self):
        CodigoPromocional.objects.create(codigo='VERANO10', porcentaje_descuento=Decimal('10'))
        body = self.get(codigo=' verano10 ', correo_cliente='ana@example.com').json()
        self.assertTrue(body['valido'])

    def test_codigo_inexistente(self):
        body = self.get(codigo='NOEXISTE', correo_cliente='ana@example.com').json()
        self.assertEqual(body, {'valido': False, 'porcentaje_descuento': None})

    def test_codigo_inactivo_da_la_misma_respuesta_generica_que_uno_inexistente(self):
        CodigoPromocional.objects.create(
            codigo='VIEJO', porcentaje_descuento=Decimal('10'), activo=False,
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
            codigo='UNAVEZ', porcentaje_descuento=Decimal('10'), usos_maximos_por_cliente=1,
        )
        crear_reserva(
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
        self.reserva = crear_reserva()

    def get(self, checkout_id):
        return self.client.get('/api/reservas/estado/', {'checkout_id': checkout_id})

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

    def test_pendiente_de_pago_repone_la_cantidad_elegida_de_extras_y_transporte(self):
        """Sin esto, recargar la pagina a medio checkout perderia la cantidad
        que el cliente ya habia elegido para un extra con `cantidad_editable`
        o para el transporte (ver fleet.ExtrasItem.cantidad_editable)."""
        licencia = ExtrasItem.objects.create(
            tipo=ExtrasItem.Tipo.LICENCIA, nombre='Licencia', precio=Decimal('450'),
            cantidad_editable=True,
        )
        ReservaExtra.objects.create(
            reserva=self.reserva, extras_item=licencia, cantidad_solicitada=2,
        )
        ReservaTransporte.objects.create(
            reserva=self.reserva, zona=TransportePrecio.Zona.CENTRO,
            direccion_personalizada='Malecon 123', personas_solicitadas=3,
        )

        body = self.get(str(self.reserva.checkout_id)).json()

        self.assertEqual(body['extras'], [{'id': licencia.pk, 'cantidad': 2}])
        self.assertEqual(body['transporte']['cantidad'], 3)

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

    def test_pagada_incluye_el_desglose_de_extras_y_transporte_ya_congelado(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.precio_total = Decimal('5400.00')
        self.reserva.monto_pagado = Decimal('5400.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.save()

        item = ExtrasItem.objects.create(
            tipo=ExtrasItem.Tipo.BRUNCH, nombre='Brunch', precio=Decimal('300'),
            cobrar_por_persona=True,
        )
        ReservaExtra.objects.create(
            reserva=self.reserva, extras_item=item,
            precio_unitario=Decimal('300'), cantidad=self.reserva.numero_personas,
        )
        ReservaTransporte.objects.create(
            reserva=self.reserva, zona=TransportePrecio.Zona.CENTRO,
            direccion_personalizada='Malecon 123', numero_personas=self.reserva.numero_personas,
            precio_calculado=Decimal('2000.00'),
        )

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertEqual(body['extras'], [
            {
                'nombre': 'Brunch', 'cobrar_por_persona': True, 'monto': '600.00',
                'cantidad': self.reserva.numero_personas,
            },
        ])
        self.assertEqual(
            body['transporte'],
            {'monto': '2000.00', 'numero_personas': self.reserva.numero_personas},
        )

    def test_pagada_sin_extras_ni_transporte_los_manda_vacios(self):
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])

        body = self.get(str(self.reserva.checkout_id)).json()
        self.assertEqual(body['extras'], [])
        self.assertIsNone(body['transporte'])

    def test_pagada_incluye_el_codigo_promocional_y_descuento_ya_congelados(self):
        promo = CodigoPromocional.objects.create(codigo='VERANO10', porcentaje_descuento=Decimal('10'))
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
class WebhookTests(TestCase):
    def setUp(self):
        Tarifa.objects.create(precio=Decimal('4500.00'))
        self.reserva = crear_reserva()
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.stripe_payment_intent_id = 'pi_1'
        self.reserva.save()

    def entregar(self, evento):
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                '/api/stripe/webhook/', '{}', content_type='application/json',
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

    @mock.patch('stripe.Refund.create')
    def test_el_mismo_evento_dos_veces_no_cobra_ni_reembolsa_de_mas(self, refund):
        self.entregar(evento_pagado(self.reserva.pk))
        self.entregar(evento_pagado(self.reserva.pk))

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        refund.assert_not_called()

    @mock.patch('stripe.Refund.create')
    def test_un_segundo_cobro_distinto_se_reembolsa(self, refund):
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_1'))
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_2'))

        refund.assert_called_once()
        self.assertEqual(refund.call_args.kwargs['payment_intent'], 'pi_2')
        # La reserva conserva el primer cobro, no se duplica el monto.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        self.assertEqual(self.reserva.stripe_payment_intent_id, 'pi_1')

    @mock.patch('stripe.Refund.create')
    def test_pago_sin_reserva_se_reembolsa(self, refund):
        self.assertEqual(self.entregar(evento_pagado(99999)).status_code, 200)
        refund.assert_called_once()

    @mock.patch('stripe.Refund.create')
    def test_si_el_dia_se_lleno_reembolsa_y_cancela(self, refund):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(fecha=self.reserva.fecha, estado=Reserva.Estado.PAGADA)

        self.entregar(evento_pagado(self.reserva.pk))

        refund.assert_called_once()
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

    @mock.patch('stripe.Refund.create')
    def test_si_el_codigo_promocional_ya_no_es_valido_reembolsa_y_cancela(self, refund):
        """El codigo se agoto (otra reserva se adelanto) entre `crear-pago` y el
        webhook: mismo remedio que el cupo lleno, con el motivo real."""
        promo = CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), usos_maximos=1,
        )
        self.reserva.codigo_promocional = promo
        self.reserva.descuento_aplicado = Decimal('450.00')
        self.reserva.precio_total = Decimal('4050.00')
        self.reserva.save()
        crear_reserva(
            fecha=self.reserva.fecha, codigo_promocional=promo, estado=Reserva.Estado.PAGADA,
        )

        self.entregar(evento_pagado(self.reserva.pk, amount=405000))

        refund.assert_called_once()
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(self.reserva.reembolsada)
        self.assertEqual(self.reserva.monto_reembolsado, Decimal('4050.00'))
        self.assertIn('codigo promocional', self.reserva.motivo_cancelacion)

    @mock.patch('stripe.Refund.create', side_effect=stripe.APIConnectionError('stripe caido'))
    def test_si_falla_el_reembolso_no_se_cancela_a_ciegas(self, refund):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(fecha=self.reserva.fecha, estado=Reserva.Estado.PAGADA)

        self.assertEqual(self.entregar(evento_pagado(self.reserva.pk)).status_code, 200)

        # Sigue pendiente_pago: no se marca reembolsada una reserva cuyo dinero
        # nunca se devolvio.
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertFalse(self.reserva.reembolsada)

    def test_registra_el_descuadre_pero_no_rebota_el_pago(self):
        with self.assertLogs('apps.payments.services', level='ERROR') as logs:
            self.entregar(evento_pagado(self.reserva.pk, amount=100000))

        self.assertIn('Descuadre', '\n'.join(logs.output))
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(self.reserva.monto_pagado, Decimal('1000.00'))
        self.assertEqual(self.reserva.saldo_pendiente, Decimal('3500.00'))

    def test_firma_invalida_responde_400(self):
        with mock.patch('stripe.Webhook.construct_event', side_effect=ValueError):
            response = self.client.post(
                '/api/stripe/webhook/', '{}', content_type='application/json',
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
class EventosDeStripeTests(TestCase):
    """Reembolsos y contracargos. Sin escuchar estos eventos, el dinero se mueve
    en Stripe y la base sigue contando otra historia."""

    def setUp(self):
        Tarifa.objects.create(precio=Decimal('4500.00'))
        self.reserva = crear_reserva(estado=Reserva.Estado.PAGADA)
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.monto_pagado = Decimal('4500.00')
        self.reserva.stripe_payment_intent_id = 'pi_1'
        self.reserva.save()

    def entregar(self, tipo, objeto):
        evento = {'id': 'evt_x', 'type': tipo, 'data': {'object': objeto}}
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                '/api/stripe/webhook/', '{}', content_type='application/json',
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
class ConciliarPagosTests(TestCase):
    """El webhook puede perderse para siempre. Sin esta red, el cliente pago y
    no tiene reserva, y nadie se entera hasta que reclama."""

    def setUp(self):
        Tarifa.objects.create(precio=Decimal('4500.00'))
        self.reserva = crear_reserva()
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

    @mock.patch('stripe.PaymentIntent.retrieve')
    def test_aplica_el_pago_que_el_webhook_nunca_entrego(self, retrieve):
        retrieve.return_value = self.intent_stripe()
        self.ejecutar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))

    @mock.patch('stripe.PaymentIntent.retrieve')
    def test_dry_run_no_toca_nada(self, retrieve):
        retrieve.return_value = self.intent_stripe()
        salida = self.ejecutar(dry_run=True)

        self.assertIn('succeeded', salida)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    @mock.patch('stripe.PaymentIntent.retrieve')
    def test_no_toca_los_que_no_se_pagaron(self, retrieve):
        retrieve.return_value = self.intent_stripe(status='requires_payment_method')
        self.ejecutar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    @mock.patch('stripe.PaymentIntent.retrieve')
    def test_ignora_las_reservas_sin_intent(self, retrieve):
        Reserva.objects.filter(pk=self.reserva.pk).update(stripe_payment_intent_id='')
        self.ejecutar()
        retrieve.assert_not_called()

    @mock.patch('stripe.PaymentIntent.retrieve')
    def test_correr_dos_veces_no_duplica_nada(self, retrieve):
        retrieve.return_value = self.intent_stripe()
        self.ejecutar()
        self.ejecutar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.monto_pagado, Decimal('4500.00'))
        # La segunda vuelta ya no la ve: dejo de estar pendiente.
        self.assertEqual(retrieve.call_count, 1)


class VersionDeApiTests(TestCase):
    """La version de la API de Stripe se fija de forma explicita.

    La libreria ya manda una por su cuenta, asi que esto no cambia el
    comportamiento — cambia de donde sale el numero. Sin fijarla, la version de
    la API viaja pegada a la de la libreria y un `pip install -U stripe` la
    moveria en silencio, sin que aparezca en ningun diff que Stripe empezo a
    contestar con otro formato.
    """

    def test_configurar_stripe_fija_llave_y_version(self):
        from apps.payments.stripe_client import configurar_stripe

        with override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_API_VERSION='2026-07-29.dahlia'):
            configurar_stripe()

        self.assertEqual(stripe.api_key, 'sk_test_x')
        self.assertEqual(stripe.api_version, '2026-07-29.dahlia')

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
