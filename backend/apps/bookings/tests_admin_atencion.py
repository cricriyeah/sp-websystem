from decimal import Decimal
from unittest import mock

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.bookings.models import Orden, Reserva
from apps.tenancy import scope
from apps.testing import EmpresaTestCase


class ReservaAdminAtencionTests(EmpresaTestCase):
    def setUp(self):
        from apps.bookings.tests import crear_reserva

        self.pendiente = crear_reserva(self.empresa)
        self.pendiente.estado = Reserva.Estado.CANCELADA
        self.pendiente.monto_pagado = Decimal('4500.00')
        self.pendiente.save(update_fields=['estado', 'monto_pagado'])
        self.pagada = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        self.pagada.monto_pagado = Decimal('4500.00')
        self.pagada.save(update_fields=['monto_pagado'])
        self.url = reverse('admin:bookings_reserva_changelist')

    def _accion(self, reserva):
        return self.client.post(self.url, {
            'action': 'confirmar_devolucion', '_selected_action': [str(reserva.pk)],
        })

    def test_filtro_muestra_cancelada_pendiente_y_excluye_pagada(self):
        self.client.force_login(self.crear_jefe())
        respuesta = self.client.get(self.url, {'requiere_atencion': 'si'})
        self.assertEqual(respuesta.status_code, 200)
        ids = {r.pk for r in respuesta.context['cl'].result_list}
        self.assertIn(self.pendiente.pk, ids)
        self.assertNotIn(self.pagada.pk, ids)
        self.assertContains(respuesta, 'Confirmar devolución')

    def test_vendedora_confirma_y_queda_en_history_sin_llamar_stripe(self):
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)
        with mock.patch('apps.payments.stripe_client.configurar_stripe') as stripe_client:
            respuesta = self._accion(self.pendiente)
        self.assertEqual(respuesta.status_code, 302)
        stripe_client.assert_not_called()
        self.pendiente.refresh_from_db()
        self.assertTrue(self.pendiente.reembolsada)
        self.assertEqual(self.pendiente.monto_reembolsado, self.pendiente.monto_pagado)
        self.assertIsNotNone(self.pendiente.reembolsada_en)
        self.assertTrue(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Reserva),
            object_id=str(self.pendiente.pk), user=vendedora,
        ).exists())

    def test_no_toca_reserva_sin_atencion(self):
        self.client.force_login(self.crear_vendedora())
        respuesta = self._accion(self.pagada)
        self.assertEqual(respuesta.status_code, 302)
        self.pagada.refresh_from_db()
        self.assertFalse(self.pagada.reembolsada)
        self.assertIsNone(self.pagada.monto_reembolsado)
        self.assertIsNone(self.pagada.reembolsada_en)
        self.assertFalse(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Reserva),
            object_id=str(self.pagada.pk),
        ).exists())


class OrdenAdminAtencionTests(TestCase):
    def setUp(self):
        from apps.bookings.tests import OrdenAdminTests

        OrdenAdminTests.setUp(self)
        with scope.con_empresa(self.a):
            self.orden.estado = Orden.Estado.CANCELADA
            self.orden.save(update_fields=['estado'])
            self.reservas[0].estado = Reserva.Estado.CANCELADA
            self.reservas[0].save(update_fields=['estado'])
        with scope.con_empresa(self.b):
            self.reservas[1].estado = Reserva.Estado.CANCELADA
            self.reservas[1].save(update_fields=['estado'])
        self.url = reverse('admin:bookings_orden_changelist')
        self.client.force_login(self.usuarios['Vendedora'])

    def test_columna_muestra_atencion_y_vendedora_ve_accion(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Confirmar devolución')
        self.assertIn('confirmar_devolucion_orden', respuesta.context['cl'].model_admin.get_actions(
            respuesta.wsgi_request,
        ))

    def test_accion_confirma_componentes_de_ambas_empresas_y_audita(self):
        with mock.patch('apps.payments.stripe_client.configurar_stripe') as stripe_client:
            respuesta = self.client.post(self.url, {
                'action': 'confirmar_devolucion_orden', '_selected_action': [str(self.orden.pk)],
            })
        self.assertEqual(respuesta.status_code, 302)
        stripe_client.assert_not_called()
        for reserva, empresa in zip(self.reservas, (self.a, self.b)):
            with scope.con_empresa(empresa):
                reserva.refresh_from_db()
            self.assertTrue(reserva.reembolsada)
            self.assertEqual(reserva.monto_reembolsado, reserva.monto_pagado)
            self.assertIsNotNone(reserva.reembolsada_en)
            self.assertTrue(LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(Reserva),
                object_id=str(reserva.pk),
            ).exists())
        self.assertTrue(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Orden),
            object_id=str(self.orden.pk),
        ).exists())

    def test_accion_no_audita_orden_sin_devoluciones_pendientes(self):
        for reserva, empresa in zip(self.reservas, (self.a, self.b)):
            with scope.con_empresa(empresa):
                reserva.monto_reembolsado = reserva.monto_pagado
                reserva.save(update_fields=['monto_reembolsado'])
        respuesta = self.client.post(self.url, {
            'action': 'confirmar_devolucion_orden', '_selected_action': [str(self.orden.pk)],
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Orden),
            object_id=str(self.orden.pk),
        ).exists())
