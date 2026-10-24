"""Una disputa perdida es dinero que Stripe se llevo: se anota aparte y Finanzas la resta."""
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.bookings.tests import crear_reserva
from apps.finance import services as finanzas
from apps.testing import ApiTestCase

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}


@override_settings(**LLAVES)
class ContracargoPerdidoTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])
        self.reserva = crear_reserva(
            self.empresa, estado=Reserva.Estado.PAGADA, stripe_payment_intent_id='pi_cp',
            monto_pagado=Decimal('4500.00'), pagada_en=timezone.now(),
        )
        Reserva.objects.filter(pk=self.reserva.pk).update(estado=Reserva.Estado.PAGADA)

    def entregar(self, tipo, **extra):
        objeto = {'id': 'dp_1', 'payment_intent': 'pi_cp', 'amount': 450000, **extra}
        evento = {'id': 'evt_cp', 'type': tipo, 'data': {'object': objeto}}
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='falsa',
            )

    def test_disputa_perdida_anota_el_monto_y_no_cambia_el_estado(self):
        self.entregar('charge.dispute.created')
        self.entregar('charge.dispute.closed', status='lost')
        self.reserva.refresh_from_db()
        self.assertFalse(self.reserva.en_disputa)
        self.assertEqual(self.reserva.contracargo_perdido, Decimal('4500.00'))
        self.assertIsNotNone(self.reserva.contracargo_perdido_en)
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)

    def test_repetir_el_evento_no_cambia_la_fecha_ni_el_monto(self):
        self.entregar('charge.dispute.closed', status='lost')
        self.reserva.refresh_from_db()
        primero = self.reserva.contracargo_perdido_en
        self.entregar('charge.dispute.closed', status='lost')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.contracargo_perdido_en, primero)
        self.assertEqual(self.reserva.contracargo_perdido, Decimal('4500.00'))

    def test_disputa_ganada_no_anota_nada(self):
        self.entregar('charge.dispute.closed', status='won')
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.contracargo_perdido)

    def test_ganar_despues_de_perder_borra_la_anotacion(self):
        self.entregar('charge.dispute.closed', status='lost')
        self.entregar('charge.dispute.funds_reinstated')
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.contracargo_perdido)
        self.assertIsNone(self.reserva.contracargo_perdido_en)

    def test_finanzas_resta_el_contracargo_de_la_cuenta_y_del_neto(self):
        self.entregar('charge.dispute.closed', status='lost')
        balance = finanzas.balances(empresa=self.empresa)[self.reserva.moneda]
        self.assertEqual(balance.tarjeta, Decimal('4500.00'))
        self.assertEqual(balance.contracargos, Decimal('4500.00'))
        self.assertEqual(balance.en_cuenta, Decimal('0.00'))
        self.assertEqual(balance.neto, Decimal('0.00'))

    def test_el_detalle_de_movimientos_cuadra_con_el_balance(self):
        self.entregar('charge.dispute.closed', status='lost')
        moneda = self.reserva.moneda
        filas = finanzas.movimientos(concepto='todos', moneda=moneda, empresa=self.empresa)
        self.assertEqual({f.concepto for f in filas}, {'tarjeta', 'contracargos'})
        totales = finanzas.totales_de_movimientos(filas, concepto='todos', moneda=moneda)
        self.assertEqual(totales[moneda], finanzas.balances(empresa=self.empresa)[moneda].neto)
