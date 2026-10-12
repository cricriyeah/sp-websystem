"""Pruebas de la liberación segura del apartado temporal y errores de concurrencia.

Spec: §4.3 (Bloque C, reglas de liberación, tabla de errores con 503 reintentar).
"""
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

import stripe
from stripe import StripeClient
from django.db import DatabaseError
from django.db.utils import OperationalError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca


def intent_falso(id='pi_1', amount=450000, status='requires_payment_method', currency='mxn'):
    return mock.Mock(id=id, amount=amount, currency=currency, status=status, client_secret=f'{id}_secret')


class ApartadoLiberacionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])

        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'),
            precio_persona_extra=Decimal('500.00'),
        )
        self.fecha = date.today() + timedelta(days=10)

    def _crear_reserva(self, **overrides):
        datos = {
            'empresa': self.empresa,
            'servicio': self.servicio,
            'fecha': self.fecha,
            'hora': time(6, 0),
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'canal_origen': Reserva.CanalOrigen.WEB,
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'checkout_id': uuid.uuid4(),
            'estado': Reserva.Estado.PENDIENTE_PAGO,
        }
        datos.update(overrides)
        reserva = Reserva(**datos)
        reserva.full_clean()
        reserva.save()
        return reserva

    def _post_crear_pago(self, reserva, **body):
        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk})
        payload = {
            'forma_pago': 'completo',
            'checkout_id': str(reserva.checkout_id),
        }
        payload.update(body)
        return self.client.post(url, payload, content_type='application/json')

    @override_settings(APARTADO_MINUTOS=15)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_stripe_falla_tras_crear_apartado_se_libera(self, payment_intents):
        reserva = self._crear_reserva()
        self.assertIsNone(reserva.apartado_hasta)

        payment_intents.create.side_effect = stripe.APIConnectionError('Fallo al conectar con Stripe')

        resp = self._post_crear_pago(reserva)
        self.assertEqual(resp.status_code, 502)

        reserva.refresh_from_db()
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    @override_settings(APARTADO_MINUTOS=15)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_stripe_falla_con_renovacion_concurrente_no_borra_apartado_renovado(self, payment_intents):
        reserva = self._crear_reserva()
        nuevo_apartado_hasta = timezone.now() + timedelta(minutes=30)
        demanda_renovada = {'v': 1, 'renovado_por_otra': True}

        def simular_carrera(*args, **kwargs):
            # Otra llamada concurrente renueva el apartado con un nuevo vencimiento
            Reserva.objects.filter(pk=reserva.pk).update(
                apartado_hasta=nuevo_apartado_hasta,
                apartado_demanda=demanda_renovada,
            )
            raise stripe.APIConnectionError('Timeout en llamada de esta petición')

        payment_intents.create.side_effect = simular_carrera

        resp = self._post_crear_pago(reserva)
        self.assertEqual(resp.status_code, 502)

        reserva.refresh_from_db()
        # La escritura condicional (WHERE apartado_hasta=<escrito>) no debió tocar el renovado
        self.assertEqual(reserva.apartado_hasta, nuevo_apartado_hasta)
        self.assertEqual(reserva.apartado_demanda, demanda_renovada)

    @override_settings(APARTADO_MINUTOS=15)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_stripe_falla_tras_solo_renovar_apartado_se_conserva(self, payment_intents):
        reserva = self._crear_reserva()
        ahora = timezone.now()
        apartado_previo = ahora + timedelta(minutes=10)
        demanda_previa = {'v': 1, 'salidas': [{'fecha': self.fecha.isoformat(), 'personas': 2}]}
        Reserva.objects.filter(pk=reserva.pk).update(
            apartado_hasta=apartado_previo,
            apartado_demanda=demanda_previa,
        )
        reserva.refresh_from_db()

        payment_intents.create.side_effect = stripe.APIConnectionError('Stripe caído')

        resp = self._post_crear_pago(reserva)
        self.assertEqual(resp.status_code, 502)

        reserva.refresh_from_db()
        # Esta llamada solo renovó: no se libera ni se borra el apartado
        self.assertIsNotNone(reserva.apartado_hasta)
        self.assertGreater(reserva.apartado_hasta, ahora)
        self.assertIsNotNone(reserva.apartado_demanda)

    @override_settings(APARTADO_MINUTOS=15)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_pago_en_curso_en_bloque_c_responde_409_sin_liberar(self, payment_intents):
        reserva = self._crear_reserva(stripe_payment_intent_id='pi_en_curso')

        # Bloque A lee el intent y está 'requires_payment_method'; en Bloque C ya pasó a 'processing'
        intent_a = intent_falso(id='pi_en_curso', status='requires_payment_method')
        intent_c = intent_falso(id='pi_en_curso', status='processing')
        payment_intents.retrieve.side_effect = [intent_a, intent_c]

        resp = self._post_crear_pago(reserva)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json().get('codigo'), 'pago_en_curso')

        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.apartado_hasta)
        self.assertIsNotNone(reserva.apartado_demanda)

    @override_settings(APARTADO_MINUTOS=15)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_carrera_a_hacia_c_rechazo_update_processing_responde_pago_en_curso_sin_liberar(self, payment_intents):
        reserva = self._crear_reserva(stripe_payment_intent_id='pi_carrera_update')

        # Bloque A y Bloque C recuperan intent con monto distinto para forzar update
        intent_obj = intent_falso(id='pi_carrera_update', amount=100000, status='requires_payment_method')
        payment_intents.retrieve.return_value = intent_obj

        # Update falla porque en Stripe el intent pasó a processing justo en ese instante
        payment_intents.update.side_effect = stripe.InvalidRequestError(
            'The PaymentIntent pi_carrera_update cannot be updated because it has a status of processing.',
            param='status',
        )

        resp = self._post_crear_pago(reserva)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json().get('codigo'), 'pago_en_curso')

        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.apartado_hasta)
        self.assertIsNotNone(reserva.apartado_demanda)

    @override_settings(APARTADO_MINUTOS=15)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_carrera_a_hacia_c_rechazo_create_processing_responde_pago_en_curso_sin_liberar(self, payment_intents):
        reserva = self._crear_reserva()

        # Create falla porque el intent asociado a la idempotency key ya está en processing
        payment_intents.create.side_effect = stripe.InvalidRequestError(
            'The PaymentIntent cannot be modified because it has a status of processing.',
            param='status',
        )

        resp = self._post_crear_pago(reserva)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json().get('codigo'), 'pago_en_curso')

        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.apartado_hasta)
        self.assertIsNotNone(reserva.apartado_demanda)

    @override_settings(APARTADO_MINUTOS=15)
    def test_lock_timeout_en_bloque_b_responde_503_reintentar(self):
        reserva = self._crear_reserva()

        with mock.patch('apps.payments.views.bloquear_cupo') as mock_bloquear:
            exc = OperationalError('canceling statement due to lock timeout\n55P03')
            exc.sqlstate = '55P03'
            mock_bloquear.side_effect = exc

            resp = self._post_crear_pago(reserva)
            self.assertEqual(resp.status_code, 503)
            self.assertEqual(resp.json().get('codigo'), 'reintentar')
            self.assertIn('detail', resp.json())

        reserva.refresh_from_db()
        self.assertIsNone(reserva.apartado_hasta)

    @override_settings(APARTADO_MINUTOS=15)
    def test_lock_timeout_con_database_error_responde_503_reintentar(self):
        reserva = self._crear_reserva()

        with mock.patch('apps.payments.views.bloquear_cupo') as mock_bloquear:
            exc = DatabaseError('canceling statement due to lock timeout')
            exc.sqlstate = '55P03'
            mock_bloquear.side_effect = exc

            resp = self._post_crear_pago(reserva)
            self.assertEqual(resp.status_code, 503)
            self.assertEqual(resp.json().get('codigo'), 'reintentar')

        reserva.refresh_from_db()
        self.assertIsNone(reserva.apartado_hasta)
