"""Efectivo capturado a mano en la reserva.

Caso real (2026-10-23): la vendedora escribia el efectivo recibido en el
formulario de la reserva y se guardaba el monto, pero no la fecha. Finanzas
descarta todo movimiento sin fecha, asi que ese dinero no existia para el panel.
"""
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.finance.services import balances
from apps.testing import EmpresaTestCase

from .models import Reserva
from .tests import crear_reserva


class SelloDeEfectivoEnElFormularioTests(EmpresaTestCase):
    def setUp(self):
        self.reserva = crear_reserva(
            self.empresa, estado=Reserva.Estado.PAGADA, forma_pago=Reserva.FormaPago.ANTICIPO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
        )
        self.url = reverse('admin:bookings_reserva_change', args=[self.reserva.pk])
        self.vendedora = self.crear_vendedora()
        self.client.force_login(self.vendedora)

    def guardar(self, **extra):
        datos = {
            'nombre_cliente': self.reserva.nombre_cliente,
            'telefono_cliente': self.reserva.telefono_cliente,
            'correo_cliente': self.reserva.correo_cliente,
            'fecha': self.reserva.fecha.isoformat(),
            'hora': self.reserva.hora.strftime('%H:%M'),
            'numero_personas': str(self.reserva.numero_personas),
            'servicio': str(self.reserva.servicio_id),
            'canal_origen': self.reserva.canal_origen,
            'estado': Reserva.Estado.PAGADA,
            'moneda': self.reserva.moneda,
            'forma_pago': Reserva.FormaPago.ANTICIPO,
            'precio_total': '4500.00',
            'monto_pagado': '1350.00',
            **extra,
        }
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None)
                         and respuesta.context['adminform'].form.errors)
        self.reserva.refresh_from_db()
        return self.reserva

    def test_el_efectivo_escrito_en_el_formulario_queda_con_fecha_y_quien_lo_recibio(self):
        antes = timezone.now()

        reserva = self.guardar(monto_efectivo='3150.00')

        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))
        self.assertIsNotNone(reserva.efectivo_cobrado_en)
        self.assertGreaterEqual(reserva.efectivo_cobrado_en, antes)
        self.assertEqual(reserva.efectivo_cobrado_por, self.vendedora)

    def test_finanzas_cuenta_el_efectivo_escrito_en_el_formulario(self):
        self.guardar(monto_efectivo='3150.00')

        hoy = timezone.localdate()
        balance = balances(hoy, hoy, empresa=self.empresa)['MXN']
        self.assertEqual(balance.efectivo, Decimal('3150.00'))
        self.assertEqual(balance.en_efectivo, Decimal('3150.00'))

    def test_corregir_el_monto_no_pisa_la_fecha_del_primer_registro(self):
        self.guardar(monto_efectivo='1000.00')
        primera = timezone.now() - timedelta(days=2)
        Reserva.objects.filter(pk=self.reserva.pk).update(efectivo_cobrado_en=primera)

        reserva = self.guardar(monto_efectivo='1500.00')

        self.assertEqual(reserva.monto_efectivo, Decimal('1500.00'))
        self.assertEqual(reserva.efectivo_cobrado_en, primera)

    def test_guardar_otra_cosa_no_vuelve_a_sellar(self):
        self.guardar(monto_efectivo='1000.00')
        primera = timezone.now() - timedelta(days=2)
        Reserva.objects.filter(pk=self.reserva.pk).update(efectivo_cobrado_en=primera)

        reserva = self.guardar(monto_efectivo='1000.00', nombre_cliente='Nombre nuevo')

        self.assertEqual(reserva.efectivo_cobrado_en, primera)

    def test_no_pisa_el_sello_que_dejo_la_accion_de_liquidar(self):
        sello = timezone.now() - timedelta(days=1)
        Reserva.objects.filter(pk=self.reserva.pk).update(
            monto_efectivo=Decimal('3150.00'), efectivo_cobrado_en=sello,
            efectivo_cobrado_por=self.vendedora)

        reserva = self.guardar(monto_efectivo='3200.00')

        self.assertEqual(reserva.efectivo_cobrado_en, sello)

    def test_un_efectivo_viejo_sin_fecha_la_recibe_al_guardar(self):
        """Filas capturadas antes del arreglo: tienen monto y no tienen fecha."""
        Reserva.objects.filter(pk=self.reserva.pk).update(monto_efectivo=Decimal('500.00'))

        reserva = self.guardar(monto_efectivo='500.00')

        self.assertIsNotNone(reserva.efectivo_cobrado_en)
        self.assertEqual(reserva.efectivo_cobrado_por, self.vendedora)

    def test_quitar_el_efectivo_borra_el_sello_para_que_un_nuevo_monto_lleve_su_fecha(self):
        self.guardar(monto_efectivo='1000.00')
        Reserva.objects.filter(pk=self.reserva.pk).update(
            efectivo_cobrado_en=timezone.now() - timedelta(days=5))

        quitado = self.guardar(monto_efectivo='')
        self.assertIsNone(quitado.efectivo_cobrado_en)
        self.assertIsNone(quitado.efectivo_cobrado_por)

        reserva = self.guardar(monto_efectivo='700.00')
        self.assertGreater(reserva.efectivo_cobrado_en, timezone.now() - timedelta(minutes=5))

    def test_sin_efectivo_no_hay_sello(self):
        reserva = self.guardar()

        self.assertIsNone(reserva.efectivo_cobrado_en)
        self.assertIsNone(reserva.efectivo_cobrado_por)
