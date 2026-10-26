"""Marcar pagada por transferencia una reserva que se quedo esperando el pago (ver `transferencia.py`)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse

from apps.testing import EmpresaTestCase, crear_flota

from .models import MovimientoDinero, Reserva
from .tests_agenda import viaje
from .transferencia import (
    ErrorDeTransferencia, marcar_pagada_por_transferencia, monto_sugerido, puede_marcarse_pagada,
)

NOTIFICAR = 'apps.bookings.transferencia.notificar_reserva_pagada'


def pendiente(empresa, **campos):
    campos.setdefault('estado', Reserva.Estado.PENDIENTE_PAGO)
    campos.setdefault('precio_total', Decimal('1000.00'))
    campos.setdefault('moneda', 'MXN')
    campos.setdefault('fecha', date.today() + timedelta(days=5))
    return viaje(empresa, **campos)


class MarcarPagadaPorTransferenciaTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()

    def test_deja_la_reserva_pagada_con_el_dinero_sellado_y_en_el_libro(self):
        reserva = pendiente(self.empresa)

        with mock.patch(NOTIFICAR, return_value={'email': True}) as avisar, self.captureOnCommitCallbacks(execute=True):
            resultado = marcar_pagada_por_transferencia(reserva.pk, '1000', self.jefe)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.monto_transferencia, Decimal('1000.00'))
        self.assertEqual(reserva.transferencia_registrada_por, self.jefe)
        self.assertIsNotNone(reserva.transferencia_registrada_en)
        self.assertEqual(reserva.monto_pagado or 0, 0)  # no es dinero de tarjeta
        self.assertIsNone(reserva.apartado_hasta)
        avisar.assert_called_once()
        self.assertEqual(resultado.resultado_notificacion, {'email': True})
        # Finanzas lee estas filas: la transferencia entra al banco con la fecha de hoy.
        fila = MovimientoDinero.objects.get(reserva=reserva, concepto=MovimientoDinero.Concepto.TRANSFERENCIA)
        self.assertEqual(fila.monto, Decimal('1000.00'))
        self.assertEqual(fila.registrado_por, self.jefe)

    def test_un_monto_menor_al_total_se_acepta_y_queda_saldo(self):
        reserva = pendiente(self.empresa)
        with mock.patch(NOTIFICAR, return_value={}), self.captureOnCommitCallbacks(execute=True):
            marcar_pagada_por_transferencia(reserva.pk, '300.50', self.jefe)

        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_transferencia, Decimal('300.50'))
        self.assertEqual(reserva.saldo_pendiente, Decimal('699.50'))

    def test_monto_invalido_o_mayor_al_total_no_cambia_nada(self):
        reserva = pendiente(self.empresa)
        for monto in ('', 'abc', '0', '-5', '1000.01'):
            with self.subTest(monto=monto), self.assertRaises(ErrorDeTransferencia):
                marcar_pagada_por_transferencia(reserva.pk, monto, self.jefe)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertFalse(MovimientoDinero.objects.filter(reserva=reserva).exists())

    def test_solo_una_reserva_esperando_el_pago(self):
        for estado in (Reserva.Estado.PAGADA, Reserva.Estado.CANCELADA, Reserva.Estado.ASIGNADA):
            with self.subTest(estado=estado):
                reserva = pendiente(self.empresa, estado=estado)
                self.assertFalse(puede_marcarse_pagada(reserva))
                with self.assertRaises(ErrorDeTransferencia):
                    marcar_pagada_por_transferencia(reserva.pk, '100', self.jefe)

    def test_dos_veces_la_segunda_no_duplica_el_dinero(self):
        reserva = pendiente(self.empresa)
        with mock.patch(NOTIFICAR, return_value={}), self.captureOnCommitCallbacks(execute=True):
            marcar_pagada_por_transferencia(reserva.pk, '1000', self.jefe)
        with self.assertRaises(ErrorDeTransferencia):
            marcar_pagada_por_transferencia(reserva.pk, '1000', self.jefe)

        self.assertEqual(MovimientoDinero.objects.filter(reserva=reserva).count(), 1)

    def test_si_no_hay_cupo_no_se_guarda_nada(self):
        from apps.bookings.cupo import SinCupoError

        reserva = pendiente(self.empresa)
        with mock.patch('apps.bookings.transferencia.reservar_cupo_al_confirmar', side_effect=SinCupoError('lleno')):
            with self.assertRaises(ErrorDeTransferencia) as ctx:
                marcar_pagada_por_transferencia(reserva.pk, '1000', self.jefe)

        self.assertIn('Ya no hay lugar', str(ctx.exception))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertIsNone(reserva.transferencia_registrada_en)

    def test_el_monto_sugerido_es_el_total(self):
        self.assertEqual(monto_sugerido(pendiente(self.empresa)), Decimal('1000.00'))


class PantallaDeTransferenciaTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.client.force_login(self.crear_jefe())
        self.reserva = pendiente(self.empresa, nombre_cliente='Ana Ruiz')
        self.url = reverse('admin:bookings_reserva_pagar_transferencia', args=[self.reserva.pk])

    def test_muestra_la_confirmacion_con_el_monto_sugerido(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Esto no cobra nada')
        self.assertContains(respuesta, 'value="1000.00"')

    def test_confirmar_deja_pagada_y_dice_que_salio_el_correo(self):
        with mock.patch('django.db.transaction.on_commit', side_effect=lambda f, *a, **k: f()), \
                mock.patch(NOTIFICAR, return_value={'email': True}):
            respuesta = self.client.post(self.url, {'monto': '1000'}, follow=True)

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('pagada por transferencia' in m and 'correo de confirmación' in m for m in mensajes), mensajes)

    def test_si_el_correo_no_sale_la_pantalla_lo_dice(self):
        with mock.patch('django.db.transaction.on_commit', side_effect=lambda f, *a, **k: f()), \
                mock.patch(NOTIFICAR, return_value={'email': False}):
            respuesta = self.client.post(self.url, {'monto': '1000'}, follow=True)

        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('No se pudo mandar el correo de confirmación' in m for m in mensajes), mensajes)

    def test_un_monto_malo_vuelve_al_formulario_con_el_error(self):
        respuesta = self.client.post(self.url, {'monto': '99999'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'mayor que el total')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    def test_una_reserva_ya_pagada_no_se_puede_marcar_otra_vez(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(estado=Reserva.Estado.PAGADA)

        respuesta = self.client.get(self.url, follow=True)

        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('ya no está esperando el pago' in m for m in mensajes), mensajes)

    def test_sin_permiso_de_cambiar_reservas_es_403(self):
        sin_permiso = self.crear_vendedora(username='lectora', permisos=[])
        from django.contrib.auth.models import Permission
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_el_resumen_de_una_reserva_pendiente_ofrece_el_boton(self):
        respuesta = self.client.get(reverse('admin:bookings_reserva_change', args=[self.reserva.pk]))

        self.assertContains(respuesta, 'Marcar pagada por transferencia')
        self.assertContains(respuesta, self.url)

    def test_el_resumen_de_una_pagada_no_lo_ofrece(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(estado=Reserva.Estado.PAGADA)

        respuesta = self.client.get(reverse('admin:bookings_reserva_change', args=[self.reserva.pk]))

        self.assertNotContains(respuesta, 'Marcar pagada por transferencia')


class AccionEnCheckoutsAbandonadosTests(EmpresaTestCase):
    def test_la_fila_ofrece_pago_por_transferencia_y_lleva_a_la_pantalla(self):
        from django.utils import timezone

        self.client.force_login(self.crear_jefe())
        reserva = pendiente(self.empresa)
        Reserva.objects.filter(pk=reserva.pk).update(creado_en=timezone.now() - timedelta(hours=5))

        lista = self.client.get(reverse('admin:bookings_checkoutabandonado_changelist'))
        self.assertContains(lista, 'Pagó por transferencia')

        accion = self.client.get(
            reverse('admin:bookings_checkoutabandonado_accion_fila_transferencia', args=[reserva.pk]))
        self.assertRedirects(
            accion, reverse('admin:bookings_reserva_pagar_transferencia', args=[reserva.pk]),
            fetch_redirect_response=False,
        )
