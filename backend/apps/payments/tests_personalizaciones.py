from decimal import Decimal
from datetime import date, time
from unittest import mock
import uuid

import stripe
from django.test import SimpleTestCase
from django.urls import reverse

from apps.bookings.models import Reserva, ReservaPersonalizacion
from apps.fleet.models import CodigoPromocional, Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.pricing import cargo_personalizacion
from apps.testing import ApiTestCase


class CantidadPersonalizacionTests(SimpleTestCase):
    def test_licencia_editable_no_multiplica_dos_veces(self):
        self.assertEqual(
            cargo_personalizacion(
                Decimal('450'),
                cobrar_por_persona=True,
                cantidad_editable=True,
                personas=5,
                cantidad=2,
            ),
            Decimal('900'),
        )

    def test_grupo_completo_ignora_cantidad_del_cliente(self):
        self.assertEqual(
            cargo_personalizacion(
                Decimal('300'),
                cobrar_por_persona=True,
                cantidad_editable=False,
                personas=5,
                cantidad=1,
            ),
            Decimal('1500'),
        )

    def test_plano_y_moneda_no_configurada(self):
        self.assertEqual(
            cargo_personalizacion(
                Decimal('200'),
                cobrar_por_persona=False,
                cantidad_editable=False,
                personas=5,
                cantidad=5,
            ),
            Decimal('200'),
        )
        self.assertIsNone(
            cargo_personalizacion(
                None,
                cobrar_por_persona=False,
                cantidad_editable=False,
                personas=5,
            )
        )


def intent_falso(id='pi_personalizaciones', amount=190000, status='requires_payment_method'):
    return mock.Mock(
        id=id, amount=amount, currency='mxn', status=status,
        client_secret=f'{id}_secret',
    )


class CrearPagoPersonalizacionesTests(ApiTestCase):
    def setUp(self):
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Tour terrestre', slug='tour-terrestre',
            tipo_servicio='otro', estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        check = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Acceso premium', tipo_interaccion='check',
            cobrar_por_persona=True, cantidad_editable=True,
        )
        self.sp_check = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=check,
            precio=Decimal('450.00'),
        )
        requerido = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Número de habitación',
            tipo_interaccion='input_numero',
        )
        self.sp_requerido = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=requerido, obligatorio=True,
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.servicio,
            fecha=date(2026, 11, 1), hora=time(9), numero_personas=5,
            nombre_cliente='Ana', telefono_cliente='1234567890',
            correo_cliente='ana@example.com', moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO, checkout_id=uuid.uuid4(),
        )
        self.check = ReservaPersonalizacion.objects.create(
            reserva=self.reserva, servicio_personalizacion=self.sp_check, cantidad=2,
        )
        self.input = ReservaPersonalizacion.objects.create(
            reserva=self.reserva, servicio_personalizacion=self.sp_requerido,
            respuesta='14',
        )
        self.url = reverse(
            'crear-pago',
            kwargs={'empresa_slug': self.empresa.slug, 'pk': self.reserva.pk},
        )

    def post(self, **extra):
        datos = {
            'checkout_id': str(self.reserva.checkout_id), 'forma_pago': 'completo',
        }
        datos.update(extra)
        return self.client.post(self.url, datos, content_type='application/json')

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_suma_checks_y_congela_precio_cantidad_solo_tras_stripe(self, configurar):
        configurar.return_value.payment_intents.create.return_value = intent_falso()

        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['monto_a_cobrar'], '1900.00')
        self.check.refresh_from_db()
        self.input.refresh_from_db()
        self.assertEqual(self.check.precio_unitario, Decimal('450.00'))
        self.assertEqual(self.check.cantidad, 2)
        self.assertIsNone(self.input.precio_unitario)

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_reintento_pendiente_recalcula_catalogo_y_actualiza_intent(self, configurar):
        cliente = configurar.return_value
        cliente.payment_intents.create.return_value = intent_falso()
        self.post()
        self.sp_check.precio = Decimal('500.00')
        self.sp_check.save(update_fields=['precio'])
        cliente.payment_intents.retrieve.return_value = intent_falso(amount=190000)
        cliente.payment_intents.update.return_value = intent_falso(amount=200000)

        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['monto_a_cobrar'], '2000.00')
        self.check.refresh_from_db()
        self.assertEqual(self.check.precio_unitario, Decimal('500.00'))
        cliente.payment_intents.update.assert_called_once()

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_promocion_y_anticipo_se_aplican_despues_de_personalizaciones(self, configurar):
        configurar.return_value.payment_intents.create.return_value = intent_falso(amount=51300)
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='DIEZ', porcentaje_descuento=Decimal('10.00'),
        )

        respuesta = self.post(forma_pago='anticipo', codigo_promocional='DIEZ')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['monto_a_cobrar'], '513.00')
        params = configurar.return_value.payment_intents.create.call_args.args[0]
        self.assertEqual(params['amount'], 51300)

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_intent_en_proceso_no_reemplaza_snapshot_previo(self, configurar):
        cliente = configurar.return_value
        cliente.payment_intents.create.return_value = intent_falso()
        self.post()
        self.sp_check.precio = Decimal('500.00')
        self.sp_check.save(update_fields=['precio'])
        cliente.payment_intents.retrieve.return_value = intent_falso(status='processing')

        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 409)
        self.check.refresh_from_db()
        self.assertEqual(self.check.precio_unitario, Decimal('450.00'))

    def test_estado_pendiente_restaura_respuestas_y_estado_pagado_usa_snapshot(self):
        url = reverse('reserva-estado', kwargs={'empresa_slug': self.empresa.slug})
        pendiente = self.client.get(url, {'checkout_id': str(self.reserva.checkout_id)})
        self.assertEqual(pendiente.status_code, 200)
        self.assertEqual(
            pendiente.json()['personalizaciones'],
            [
                {'id': self.sp_check.id, 'cantidad': 2, 'respuesta': ''},
                {'id': self.sp_requerido.id, 'cantidad': 1, 'respuesta': '14'},
            ],
        )

        self.check.precio_unitario = Decimal('450.00')
        self.check.save(update_fields=['precio_unitario'])
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])
        pagada = self.client.get(url, {'checkout_id': str(self.reserva.checkout_id)})
        filas = pagada.json()['personalizaciones']
        self.assertEqual(filas[0]['monto'], '900.00')
        self.assertEqual(filas[1]['respuesta'], '14')
        self.assertIsNone(filas[1]['monto'])

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_error_stripe_no_congela_ni_guarda_total(self, configurar):
        configurar.return_value.payment_intents.create.side_effect = stripe.StripeError('falló')

        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 502)
        self.check.refresh_from_db()
        self.reserva.refresh_from_db()
        self.assertIsNone(self.check.precio_unitario)
        self.assertIsNone(self.reserva.precio_total)

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_moneda_sin_tipo_de_cambio_no_llama_stripe(self, configurar):
        self.reserva.moneda = 'USD'
        self.reserva.save(update_fields=['moneda'])
        Reserva.objects.filter(pk=self.reserva.pk).update(tipo_cambio=None)  # fila anterior al tipo de cambio

        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 503)
        configurar.assert_not_called()
    @mock.patch('apps.payments.views.configurar_stripe')
    def test_input_obligatorio_agregado_despues_bloquea_el_pago(self, configurar):
        self.input.delete()

        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 503)
        self.assertIn('Falta responder', respuesta.json()['detail'])
        configurar.assert_not_called()


class CrearPagoPaquetePersonalizacionesTests(ApiTestCase):
    def setUp(self):
        from apps.fleet.models import Paquete, PaqueteServicio

        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])

        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Paquete', slug='pesca-paquete',
            tipo_servicio='pesca', estrategia_cupo='cupo_diario',
            precio_base=Decimal('5000.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.empresa.sede, empresa_lider=self.empresa,
            nombre='Pack Pesca VIP', slug='pack-pesca-vip',
            precio_ancla=Decimal('6000.00'),
        )
        self.ps = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio, orden=1,
        )

        pers_licencia = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Licencia VIP', tipo_interaccion='check',
            cobrar_por_persona=True, cantidad_editable=True,
        )
        self.sp_licencia = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=pers_licencia,
            precio=Decimal('450.00'),
            preseleccionado=True, activo=True,
        )

        self.reserva = Reserva.objects.create(
            empresa=self.empresa, paquete=self.paquete, servicio=None,
            fecha=date(2026, 11, 1), hora=time(6), numero_personas=2,
            nombre_cliente='Carlos', telefono_cliente='1234567890',
            correo_cliente='carlos@example.com', moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO, checkout_id=uuid.uuid4(),
        )
        self.check = ReservaPersonalizacion.objects.create(
            reserva=self.reserva, servicio_personalizacion=self.sp_licencia, cantidad=2,
        )
        self.url = reverse(
            'crear-pago',
            kwargs={'empresa_slug': self.empresa.slug, 'pk': self.reserva.pk},
        )

    def post(self, **extra):
        datos = {
            'checkout_id': str(self.reserva.checkout_id), 'forma_pago': 'completo',
        }
        datos.update(extra)
        return self.client.post(self.url, datos, content_type='application/json')

    @mock.patch('apps.payments.views.configurar_stripe')
    def test_pago_paquete_cobra_ancla_mas_seleccion_y_congela_snapshot(self, configurar):
        configurar.return_value.payment_intents.create.return_value = intent_falso(amount=690000)

        # Ancla 6000 + licencia (450 * 2 = 900) = 6900.00 (no doble cobro ni 7800 ni 10500)
        respuesta = self.post()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['monto_a_cobrar'], '6900.00')

        self.check.refresh_from_db()
        self.assertEqual(self.check.precio_unitario, Decimal('450.00'))
        self.assertEqual(self.check.cantidad, 2)

        # Cambio posterior de catálogo no altera estado ni snapshot
        self.sp_licencia.precio = Decimal('999.00')
        self.sp_licencia.save(update_fields=['precio'])
        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save(update_fields=['estado'])

        url_estado = reverse('reserva-estado', kwargs={'empresa_slug': self.empresa.slug})
        resp_pagada = self.client.get(url_estado, {'checkout_id': str(self.reserva.checkout_id)})
        self.assertEqual(resp_pagada.json()['estado'], 'pagada')
        self.assertEqual(resp_pagada.json()['personalizaciones'][0]['monto'], '900.00')

    def test_recuperacion_lista_vacia_permanece_vacia(self):
        self.check.delete()
        url_estado = reverse('reserva-estado', kwargs={'empresa_slug': self.empresa.slug})
        resp = self.client.get(url_estado, {'checkout_id': str(self.reserva.checkout_id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['personalizaciones'], [])
