"""Una disputa se ve, pero no cambia el estado de la reserva: que hacer con un
viaje en contracargo lo decide una persona (backend/CLAUDE.md, «Garantias del cobro»)."""
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, Reserva
from apps.bookings.tests import crear_reserva
from apps.testing import ApiTestCase

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}


@override_settings(**LLAVES)
class DisputaNoCambiaElEstadoTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])

    def entregar(self, tipo, intent):
        evento = {'id': 'evt_d', 'type': tipo, 'data': {'object': {'id': 'dp_1', 'payment_intent': intent}}}
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='falsa',
            )

    def reserva(self, estado, intent):
        reserva = crear_reserva(self.empresa, estado=estado, stripe_payment_intent_id=intent)
        Reserva.objects.filter(pk=reserva.pk).update(estado=estado)
        return reserva

    def test_ninguna_etapa_de_la_disputa_cambia_el_estado(self):
        for n, estado in enumerate((Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA,
                                    Reserva.Estado.COMPLETADA)):
            intent = f'pi_d{n}'
            with self.subTest(estado=estado):
                reserva = self.reserva(estado, intent)
                for tipo in ('charge.dispute.created', 'charge.dispute.closed',
                             'charge.dispute.funds_reinstated', 'charge.dispute.created'):
                    self.entregar(tipo, intent)
                    reserva.refresh_from_db()
                    self.assertEqual(reserva.estado, estado, tipo)
                    self.assertFalse(reserva.reembolsada, tipo)
                    self.assertIn(reserva.estado, ESTADOS_QUE_OCUPAN_CUPO)

    def test_la_bandera_sube_y_baja_con_la_disputa(self):
        reserva = self.reserva(Reserva.Estado.ASIGNADA, 'pi_d9')

        self.entregar('charge.dispute.created', 'pi_d9')
        reserva.refresh_from_db()
        self.assertTrue(reserva.en_disputa)

        self.entregar('charge.dispute.funds_reinstated', 'pi_d9')
        reserva.refresh_from_db()
        self.assertFalse(reserva.en_disputa)
        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)
