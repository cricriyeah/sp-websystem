"""Pruebas del webhook de Stripe y conciliación con el apartado temporal de cupo (Tarea 07)."""

import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

import stripe
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from stripe import StripeClient

from apps.bookings.cupo.apartado import (
    construir_retrato_hospedaje,
    construir_retrato_servicio_suelto,
)
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.bookings.models import (
    CupoDiario,
    Reserva,
    ReservaOcupacion,
    evaluar_cupo,
)
from apps.fleet.models import Recurso, Servicio
from apps.payments.services import (
    APLICADO,
    SIN_CUPO_REEMBOLSADO,
    aplicar_pago_exitoso,
)
from apps.tenancy import scope
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}


@override_settings(APARTADO_MINUTOS=15, **LLAVES)
class ApartadoWebhookTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(
            update_fields=['stripe_secret_key', 'stripe_webhook_secret', 'stripe_publishable_key']
        )

        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'),
            precio_persona_extra=Decimal('500.00'),
        )
        self.fecha_viaje = date.today() + timedelta(days=10)

    def _crear_reserva(self, nombre='Ana Ruiz', fecha=None, personas=2, servicio=None, **extra):
        f = fecha or self.fecha_viaje
        s = servicio or self.servicio
        cid = extra.pop('checkout_id', uuid.uuid4())
        pi_id = extra.pop('stripe_payment_intent_id', f'pi_{uuid.uuid4().hex[:8]}')
        datos = {
            'empresa': self.empresa,
            'servicio': s,
            'fecha': f,
            'hora': time(6, 0),
            'numero_personas': personas,
            'nombre_cliente': nombre,
            'telefono_cliente': '+5216121234567',
            'correo_cliente': f'{nombre.lower().replace(" ", ".")}@example.com',
            'canal_origen': Reserva.CanalOrigen.WEB,
            'deslinde_aceptado': True,
            'deslinde_nombre': nombre,
            'checkout_id': cid,
            'moneda': 'MXN',
            'precio_total': Decimal('4500.00'),
            'forma_pago': Reserva.FormaPago.COMPLETO,
            'stripe_payment_intent_id': pi_id,
            'estado': Reserva.Estado.PENDIENTE_PAGO,
        }
        datos.update(extra)
        reserva = Reserva(**datos)
        reserva.full_clean()
        reserva.save()
        return reserva

    def _entregar_webhook(self, reserva, amount=450000):
        evento = {
            'id': f'evt_{uuid.uuid4().hex[:8]}',
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': reserva.stripe_payment_intent_id,
                    'amount_received': amount,
                    'currency': reserva.moneda.lower(),
                    'metadata': {'reserva_id': str(reserva.pk)},
                    'created': int(timezone.now().timestamp()),
                }
            },
        }
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}',
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='falsa',
            )

    def _mock_intent(self, reserva, amount=450000, status='succeeded'):
        return stripe.PaymentIntent.construct_from(
            {
                'id': reserva.stripe_payment_intent_id,
                'status': status,
                'amount_received': amount,
                'currency': reserva.moneda.lower(),
                'metadata': {'reserva_id': str(reserva.pk)},
                'created': int(timezone.now().timestamp()),
            },
            'sk_test_falsa',
        )

    def _ejecutar_conciliar_pagos(self):
        self._alcance.__exit__(None, None, None)
        try:
            call_command('conciliar_pagos', stdout=StringIO(), stderr=StringIO())
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_apartado_vigente_se_confirma_y_limpia_campos(self):
        """Con apartado vigente la reserva se confirma y se limpian los dos campos."""
        reserva = self._crear_reserva(nombre='Ana Ruiz')
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        resp = self._entregar_webhook(reserva)
        self.assertEqual(resp.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.monto_pagado, Decimal('4500.00'))
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_apartado_vencido_con_lugar_libre_se_confirma_y_limpia_campos(self):
        """Con apartado vencido y el lugar libre se confirma y se limpian los campos."""
        reserva = self._crear_reserva(nombre='Carlos Gomez')
        reserva.apartado_hasta = timezone.now() - timedelta(minutes=5)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        resp = self._entregar_webhook(reserva)
        self.assertEqual(resp.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.monto_pagado, Decimal('4500.00'))
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    @mock.patch.object(StripeClient, 'refunds')
    def test_apartado_vencido_con_otro_cliente_apartado_vigente_reembolsa_y_limpia_campos(
        self, refunds
    ):
        """Consecuencia intencional del spec (§4.4): con apartado vencido y otro cliente con
        apartado VIGENTE sobre el último lugar ⇒ se reembolsa y se limpian los campos."""
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=1,
        )

        reserva_vencida = self._crear_reserva(nombre='Beatriz Soto', stripe_payment_intent_id='pi_vencida')
        reserva_vencida.apartado_hasta = timezone.now() - timedelta(minutes=10)
        reserva_vencida.apartado_demanda = construir_retrato_servicio_suelto(reserva_vencida)
        reserva_vencida.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        reserva_vigente = self._crear_reserva(nombre='Daniel Vega', stripe_payment_intent_id='pi_vigente')
        reserva_vigente.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva_vigente.apartado_demanda = construir_retrato_servicio_suelto(reserva_vigente)
        reserva_vigente.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        resp = self._entregar_webhook(reserva_vencida)
        self.assertEqual(resp.status_code, 200)

        refunds.create.assert_called_once()
        reserva_vencida.refresh_from_db()
        self.assertEqual(reserva_vencida.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva_vencida.reembolsada)
        self.assertEqual(reserva_vencida.monto_reembolsado, Decimal('4500.00'))
        self.assertIsNone(reserva_vencida.apartado_hasta)
        self.assertIsNone(reserva_vencida.apartado_demanda)
        self.assertIn('cupo', reserva_vencida.motivo_cancelacion.lower())

        # El cliente con apartado vigente sigue protegido
        reserva_vigente.refresh_from_db()
        self.assertEqual(reserva_vigente.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertIsNotNone(reserva_vigente.apartado_hasta)
        self.assertIsNotNone(reserva_vigente.apartado_demanda)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cliente_con_apartado_vigente_protegido_frente_a_tercero(self, payment_intents):
        """Un cliente con apartado vigente gana frente a un tercero que intenta apartar
        el mismo lugar, y el titular se confirma exitosamente al recibir su pago."""
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=1,
        )

        reserva_titular = self._crear_reserva(nombre='Elena Morales', stripe_payment_intent_id='pi_titular')
        reserva_titular.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva_titular.apartado_demanda = construir_retrato_servicio_suelto(reserva_titular)
        reserva_titular.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        reserva_tercero = self._crear_reserva(nombre='Fernando Paz', stripe_payment_intent_id='')
        url_tercero = reverse(
            'crear-pago',
            kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva_tercero.pk},
        )
        resp_tercero = self.client.post(
            url_tercero,
            {'forma_pago': 'completo', 'checkout_id': str(reserva_tercero.checkout_id)},
            content_type='application/json',
        )
        self.assertEqual(resp_tercero.status_code, 409)
        self.assertEqual(resp_tercero.json().get('codigo'), 'sin_cupo')

        reserva_tercero.refresh_from_db()
        self.assertIsNone(reserva_tercero.apartado_hasta)
        self.assertIsNone(reserva_tercero.apartado_demanda)

        resp_titular = self._entregar_webhook(reserva_titular)
        self.assertEqual(resp_titular.status_code, 200)

        reserva_titular.refresh_from_db()
        self.assertEqual(reserva_titular.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(reserva_titular.apartado_hasta)
        self.assertIsNone(reserva_titular.apartado_demanda)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_conciliar_pagos_con_apartado_vigente_confirma_y_limpia_campos(
        self, payment_intents
    ):
        """conciliar_pagos aplica las mismas reglas: con apartado vigente confirma y limpia campos."""
        reserva = self._crear_reserva(nombre='Gabriel Torres', stripe_payment_intent_id='pi_conciliar_vig')
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        payment_intents.retrieve.return_value = self._mock_intent(reserva)

        self._ejecutar_conciliar_pagos()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.monto_pagado, Decimal('4500.00'))
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    @mock.patch.object(StripeClient, 'refunds')
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_conciliar_pagos_con_apartado_vencido_y_otro_vigente_reembolsa_y_limpia(
        self, payment_intents, refunds
    ):
        """conciliar_pagos con apartado vencido y otro cliente con apartado vigente reembolsa y limpia."""
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=1,
        )

        reserva_r1 = self._crear_reserva(nombre='Hector Ramos', stripe_payment_intent_id='pi_conciliar_venc')
        reserva_r1.apartado_hasta = timezone.now() - timedelta(minutes=10)
        reserva_r1.apartado_demanda = construir_retrato_servicio_suelto(reserva_r1)
        reserva_r1.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        reserva_r2 = self._crear_reserva(nombre='Isabel Luna', stripe_payment_intent_id='pi_conciliar_otro')
        reserva_r2.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva_r2.apartado_demanda = construir_retrato_servicio_suelto(reserva_r2)
        reserva_r2.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        intent_r1 = self._mock_intent(reserva_r1)
        payment_intents.retrieve.side_effect = lambda pi_id, **kwargs: (
            intent_r1 if pi_id == reserva_r1.stripe_payment_intent_id else mock.Mock(status='requires_payment_method')
        )

        self._ejecutar_conciliar_pagos()

        refunds.create.assert_called_once()
        reserva_r1.refresh_from_db()
        self.assertEqual(reserva_r1.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva_r1.reembolsada)
        self.assertIsNone(reserva_r1.apartado_hasta)
        self.assertIsNone(reserva_r1.apartado_demanda)

        reserva_r2.refresh_from_db()
        self.assertEqual(reserva_r2.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertIsNotNone(reserva_r2.apartado_hasta)
        self.assertIsNotNone(reserva_r2.apartado_demanda)

    @override_settings(APARTADO_MINUTOS=0, **LLAVES)
    def test_apartado_minutos_cero_ignora_apartados_existentes(self):
        """Con APARTADO_MINUTOS=0 el motor ignora cualquier apartado existente y el webhook confirma."""
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=1,
        )

        # R2 tiene un apartado grabado en base de datos
        reserva_r2 = self._crear_reserva(nombre='Jorge Silva', stripe_payment_intent_id='pi_bloqueador')
        reserva_r2.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva_r2.apartado_demanda = construir_retrato_servicio_suelto(reserva_r2)
        reserva_r2.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        # R1 llega a pagar
        reserva_r1 = self._crear_reserva(nombre='Karla Nunez', stripe_payment_intent_id='pi_pagadora')

        resp = self._entregar_webhook(reserva_r1)
        self.assertEqual(resp.status_code, 200)

        reserva_r1.refresh_from_db()
        self.assertEqual(reserva_r1.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(reserva_r1.apartado_hasta)
        self.assertIsNone(reserva_r1.apartado_demanda)

    def test_hospedaje_con_apartado_vigente_confirma_y_limpia_campos(self):
        """En hospedaje, con apartado vigente se confirma, crea ReservaOcupacion y limpia campos."""
        s_hotel = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Cabana Del Sol',
            slug='cabana-sol',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('2000.00'),
            activo=True,
        )
        recurso = Recurso.objects.create(
            empresa=self.empresa,
            servicio=s_hotel,
            nombre='Cabana Principal',
            capacidad_maxima=2,
            activo=True,
        )
        check_in = self.fecha_viaje
        check_out = self.fecha_viaje + timedelta(days=2)
        reserva = self._crear_reserva(
            nombre='Lucia Mendez',
            fecha=check_in,
            fecha_salida=check_out,
            servicio=s_hotel,
            precio_total=Decimal('4000.00'),
            stripe_payment_intent_id='pi_hotel_vig',
        )
        reserva.apartado_demanda = construir_retrato_hospedaje(reserva)
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        resp = self._entregar_webhook(reserva, amount=400000)
        self.assertEqual(resp.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)
        self.assertEqual(reserva.ocupaciones.count(), 1)
        oc = reserva.ocupaciones.first()
        self.assertEqual(oc.recurso_id, recurso.pk)
        self.assertEqual(oc.fecha_inicio, check_in)
        self.assertEqual(oc.fecha_fin, check_out)
        self.assertTrue(oc.ocupa_cupo)

    @mock.patch.object(StripeClient, 'refunds')
    def test_hospedaje_con_apartado_vencido_y_otro_vigente_reembolsa_y_limpia(
        self, refunds
    ):
        """En hospedaje, con apartado vencido y otra reserva con apartado vigente en la
        misma habitación se reembolsa y se limpian los campos."""
        s_hotel = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Bungalow Mar',
            slug='bungalow-mar',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('2000.00'),
            activo=True,
        )
        Recurso.objects.create(
            empresa=self.empresa,
            servicio=s_hotel,
            nombre='Bungalow Unico',
            capacidad_maxima=2,
            activo=True,
        )
        check_in = self.fecha_viaje
        check_out = self.fecha_viaje + timedelta(days=2)

        reserva_vencida = self._crear_reserva(
            nombre='Manuel Castro',
            fecha=check_in,
            fecha_salida=check_out,
            servicio=s_hotel,
            precio_total=Decimal('4000.00'),
            stripe_payment_intent_id='pi_hotel_venc',
        )
        reserva_vencida.apartado_demanda = construir_retrato_hospedaje(reserva_vencida)
        reserva_vencida.apartado_hasta = timezone.now() - timedelta(minutes=10)
        reserva_vencida.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        reserva_vigente = self._crear_reserva(
            nombre='Nora Rios',
            fecha=check_in,
            fecha_salida=check_out,
            servicio=s_hotel,
            precio_total=Decimal('4000.00'),
            stripe_payment_intent_id='pi_hotel_vigente',
        )
        reserva_vigente.apartado_demanda = construir_retrato_hospedaje(reserva_vigente)
        reserva_vigente.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva_vigente.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        resp = self._entregar_webhook(reserva_vencida, amount=400000)
        self.assertEqual(resp.status_code, 200)

        refunds.create.assert_called_once()
        reserva_vencida.refresh_from_db()
        self.assertEqual(reserva_vencida.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva_vencida.reembolsada)
        self.assertIsNone(reserva_vencida.apartado_hasta)
        self.assertIsNone(reserva_vencida.apartado_demanda)
        self.assertEqual(reserva_vencida.ocupaciones.count(), 0)

    def test_evaluacion_cupo_excluye_apartado_propio(self):
        """Verifica que el motor excluye la propia reserva al contar apartados vigentes."""
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=1,
        )
        reserva = self._crear_reserva(nombre='Oscar Benitez')
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        # Con excluir_pk=reserva.pk no debe reportar lleno
        motivo = evaluar_cupo(
            self.fecha_viaje,
            reserva.numero_personas,
            self.empresa,
            excluir_pk=reserva.pk,
        )
        self.assertIsNone(motivo)

        # Sin excluir_pk reporta lleno porque el apartado propio cuenta
        motivo_sin_excluir = evaluar_cupo(
            self.fecha_viaje,
            reserva.numero_personas,
            self.empresa,
            excluir_pk=None,
        )
        self.assertIsNotNone(motivo_sin_excluir)
