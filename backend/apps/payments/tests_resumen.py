import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import stripe
from django.test import TestCase
from django.utils import timezone

from apps.bookings.models import Orden, Reserva
from apps.payments.ordenes import ORDEN_TIMEOUT_AUTORIZACION
from apps.payments.situacion import Situacion, requiere_atencion
from apps.payments.tests import TrasladoPagoFixture
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import ApiTestCase


class ResumenReservaTest(TrasladoPagoFixture, ApiTestCase):
    def test_sin_pago(self):
        reserva = self.reserva()
        r = self.client.get(f'/api/{self.empresa.slug}/reservas/resumen/?checkout_id={reserva.checkout_id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.SIN_PAGO)
        self.assertIsNone(r.json()['monto'])
        self.assertEqual(r.json()['producto'], self.servicio.nombre)
        self.assertEqual(r.json()['folio'], reserva.id)
        self.assertIsNone(r.json()['vence_en'])
        self.assertNotIn('nombre_cliente', r.json())

    def test_no_existe(self):
        r = self.client.get(f'/api/{self.empresa.slug}/reservas/resumen/?checkout_id={uuid.uuid4()}')
        self.assertEqual(r.status_code, 404)

    def test_confirmada(self):
        reserva = self.reserva()
        reserva.estado = 'pagada'
        reserva.monto_pagado = 4500
        reserva.save(update_fields=['estado', 'monto_pagado'])
        r = self.client.get(f'/api/{self.empresa.slug}/reservas/resumen/?checkout_id={reserva.checkout_id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.CONFIRMADA)
        self.assertEqual(r.json()['monto'], '4500.00')

    def test_reserva_de_otra_empresa_da_404(self):
        reserva = self.reserva()
        otra = Empresa.objects.create(sede=self.sede, nombre='Otra empresa', slug='otra-empresa-resumen', activo=True)
        # ApiTestCase mantiene activo el alcance de self.empresa durante el test.
        self._alcance.__exit__(None, None, None)
        try:
            r = self.client.get(f'/api/{otra.slug}/reservas/resumen/?checkout_id={reserva.checkout_id}')
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.assertEqual(r.status_code, 404)


class ResumenOrdenTest(TestCase):
    def setUp(self):
        from apps.payments.tests import OrdenesModuloTest

        OrdenesModuloTest.setUp(self)
        self.checkout_id = uuid.uuid4()
        with scope.con_empresa(self.empresa_1):
            self.orden.checkout_id = self.checkout_id
            self.orden.save(update_fields=['checkout_id'])
        self.cliente_1 = mock.Mock()
        self.cliente_2 = mock.Mock()
        self.stripe_vistas = self.enterContext(mock.patch('apps.payments.views.configurar_stripe'))
        self.stripe_ordenes = self.enterContext(mock.patch('apps.payments.ordenes.configurar_stripe'))
        for parche in (self.stripe_vistas, self.stripe_ordenes):
            parche.side_effect = lambda emp: self.cliente_1 if emp.id == self.empresa_1.id else self.cliente_2

    def _url_resumen(self):
        return f'/api/{self.sede.slug}/ordenes/resumen/?checkout_id={self.checkout_id}'

    def _url_cancelar(self):
        return f'/api/{self.sede.slug}/ordenes/{self.orden.pk}/cancelar/'

    def _poner_intent(self, reserva, empresa, pi_id):
        with scope.con_empresa(empresa):
            reserva.stripe_payment_intent_id = pi_id
            reserva.save(update_fields=['stripe_payment_intent_id'])

    def _intent(self, cliente, pi_id, estado, centavos):
        cliente.payment_intents.retrieve.return_value = SimpleNamespace(
            id=pi_id, status=estado, client_secret=f'{pi_id}_secret', amount=centavos,
        )

    def test_armando_sin_pago_y_contrato_completo(self):
        r = self.client.get(self._url_resumen())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.SIN_PAGO)
        self.assertEqual(r.json()['producto'], self.paquete.nombre)
        self.assertEqual(r.json()['folio'], self.orden.id)
        self.assertEqual(len(r.json()['montos']), 2)
        self.assertIsNone(r.json()['vence_en'])
        self.assertNotIn('nombre_cliente', r.json())

    def test_no_existe(self):
        r = self.client.get(f'/api/{self.sede.slug}/ordenes/resumen/?checkout_id={uuid.uuid4()}')
        self.assertEqual(r.status_code, 404)

    def test_autorizando_parcial_vence_desde_actualizado_en(self):
        self._poner_intent(self.reserva_1, self.empresa_1, 'pi_resumen_1')
        self._poner_intent(self.reserva_2, self.empresa_2, 'pi_resumen_2')
        self._intent(self.cliente_1, 'pi_resumen_1', 'requires_capture', 700000)
        self._intent(self.cliente_2, 'pi_resumen_2', 'requires_payment_method', 300000)
        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.AUTORIZANDO
            self.orden.save(update_fields=['estado'])
            ahora = timezone.now()
            actualizado = ahora - timedelta(hours=1)
            Orden.objects.filter(pk=self.orden.pk).update(
                actualizado_en=actualizado, creado_en=ahora - timedelta(hours=30),
            )
        r = self.client.get(self._url_resumen())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.RETENIDO_PARCIAL)
        self.assertEqual(r.json()['vence_en'], (actualizado + ORDEN_TIMEOUT_AUTORIZACION).isoformat())
        self.assertGreater(actualizado + ORDEN_TIMEOUT_AUTORIZACION, ahora)
        self.assertEqual([m['monto'] for m in r.json()['montos']], ['7000', '3000'])

    def test_autorizando_todos_retenidos_confirma_cobro(self):
        self._poner_intent(self.reserva_1, self.empresa_1, 'pi_resumen_1')
        self._poner_intent(self.reserva_2, self.empresa_2, 'pi_resumen_2')
        self._intent(self.cliente_1, 'pi_resumen_1', 'requires_capture', 700000)
        self._intent(self.cliente_2, 'pi_resumen_2', 'requires_capture', 300000)
        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.AUTORIZANDO
            self.orden.save(update_fields=['estado'])
        r = self.client.get(self._url_resumen())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.CONFIRMANDO_COBRO)
        self.assertIsNone(r.json()['vence_en'])

    def test_cancelar_con_checkout_correcto_devuelve_resumen_completo(self):
        with mock.patch('apps.payments.ordenes.revertir_orden') as revertir:
            r = self.client.post(self._url_cancelar(), {'checkout_id': str(self.checkout_id)}, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        revertir.assert_called_once()
        self.assertEqual(r.json()['producto'], self.paquete.nombre)
        self.assertEqual(r.json()['folio'], self.orden.id)
        self.assertEqual(len(r.json()['montos']), 2)
        self.assertIn('situacion', r.json())

    def test_cancelar_con_checkout_equivocado_da_403_sin_revertir(self):
        with mock.patch('apps.payments.ordenes.revertir_orden') as revertir:
            r = self.client.post(self._url_cancelar(), {'checkout_id': str(uuid.uuid4())}, content_type='application/json')
        self.assertEqual(r.status_code, 403)
        revertir.assert_not_called()

    def test_void_fallido_nunca_dice_liberada(self):
        self._poner_intent(self.reserva_1, self.empresa_1, 'pi_void_fallido')
        self._intent(self.cliente_1, 'pi_void_fallido', 'requires_capture', 700000)
        self.cliente_1.payment_intents.cancel.side_effect = stripe.StripeError('falló void')
        r = self.client.post(self._url_cancelar(), {'checkout_id': str(self.checkout_id)}, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(r.json()['situacion']))
        self.assertEqual(r.json()['folio'], self.orden.id)
        self.assertEqual(len(r.json()['montos']), 2)
        with scope.con_empresa(self.empresa_1):
            self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

    def test_cancelar_orden_capturada_da_409_con_resumen_actual(self):
        with scope.con_empresa(self.empresa_1):
            self.orden.estado = Orden.Estado.CAPTURADA
            self.orden.save(update_fields=['estado'])
        r = self.client.post(self._url_cancelar(), {'checkout_id': str(self.checkout_id)}, content_type='application/json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['situacion'], Situacion.CONFIRMADA)
        self.assertEqual(r.json()['producto'], self.paquete.nombre)
        self.assertEqual(r.json()['folio'], self.orden.id)
        self.assertEqual(len(r.json()['montos']), 2)
        self.stripe_ordenes.assert_not_called()

    def test_get_orden_conserva_respuesta_tras_extraer_helper(self):
        self._poner_intent(self.reserva_1, self.empresa_1, 'pi_detalle_1')
        self._poner_intent(self.reserva_2, self.empresa_2, 'pi_detalle_2')
        self._intent(self.cliente_1, 'pi_detalle_1', 'requires_capture', 700000)
        self._intent(self.cliente_2, 'pi_detalle_2', 'requires_payment_method', 300000)
        r = self.client.get(f'/api/{self.sede.slug}/ordenes/{self.orden.pk}/')
        self.assertEqual(r.status_code, 200)
        with scope.con_empresa(self.empresa_1):
            self.orden.refresh_from_db()
        self.assertEqual(r.json(), {
            'id': self.orden.id, 'checkout_id': str(self.checkout_id), 'estado': Orden.Estado.ARMANDO,
            'vence_en': (self.orden.actualizado_en + ORDEN_TIMEOUT_AUTORIZACION).isoformat(),
            'reservas': [
                {'reserva_id': self.reserva_1.id, 'empresa_slug': self.empresa_1.slug,
                 'servicio': self.servicio_1.slug,
                 'pago': {'estado_pi': 'requires_capture', 'client_secret': 'pi_detalle_1_secret',
                          'publishable_key': self.empresa_1.stripe_publishable_key, 'monto': '7000'}},
                {'reserva_id': self.reserva_2.id, 'empresa_slug': self.empresa_2.slug,
                 'servicio': self.servicio_2.slug,
                 'pago': {'estado_pi': 'requires_payment_method', 'client_secret': 'pi_detalle_2_secret',
                          'publishable_key': self.empresa_2.stripe_publishable_key, 'monto': '3000'}},
            ],
        })
