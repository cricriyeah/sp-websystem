"""El dinero que llega en dos momentos cae en el dia de cada momento.

Una reserva guarda UN total por concepto y la fecha del primer registro: si la vendedora anota $500 el
lunes y completa $700 el viernes, Finanzas contaba los $1,200 el lunes (y el viernes quedaba en cero).
`MovimientoDinero` fecha cada cambio de monto; estas pruebas fijan que el total nunca cambia y que
el reparto por dia sigue a la realidad.
"""
from decimal import Decimal
from unittest import mock

from apps.bookings.models import MovimientoDinero, Reserva
from apps.testing import EmpresaTestCase

from .services import balances, balances_por_dia, movimientos, totales_de_movimientos
from .tests import crear_reserva, momento

LUNES = momento(2026, 3, 2)
VIERNES = momento(2026, 3, 6)


def en(instante):
    """Congela `timezone.now()` del modelo en `instante`."""
    return mock.patch('apps.bookings.models.timezone.now', return_value=instante)


def recargar(reserva):
    return Reserva.objects.get(pk=reserva.pk)


class LibroDeMovimientosTests(EmpresaTestCase):
    def total(self, atributo, dia):
        saldo = balances(dia, dia, empresa=self.empresa).get('MXN')
        return getattr(saldo, atributo) if saldo else Decimal('0.00')

    def test_efectivo_en_dos_partes_cae_en_cada_dia(self):
        reserva = crear_reserva(self.empresa, monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=LUNES)

        reserva = recargar(reserva)
        reserva.monto_efectivo = Decimal('1200.00')
        with en(VIERNES):
            reserva.save()

        self.assertEqual(self.total('efectivo', LUNES.date()), Decimal('500.00'))
        self.assertEqual(self.total('efectivo', VIERNES.date()), Decimal('700.00'))
        self.assertEqual(balances(empresa=self.empresa)['MXN'].efectivo, Decimal('1200.00'))

    def test_segundo_reembolso_parcial_no_mueve_el_primero(self):
        reserva = crear_reserva(
            self.empresa, monto_pagado=Decimal('2000.00'), pagada_en=LUNES,
            monto_reembolsado=Decimal('300.00'), reembolsada_en=LUNES,
        )

        reserva = recargar(reserva)
        reserva.monto_reembolsado = Decimal('800.00')
        reserva.reembolsada_en = VIERNES
        with en(VIERNES):
            reserva.save(update_fields=['monto_reembolsado', 'reembolsada_en'])

        self.assertEqual(self.total('reembolsos', LUNES.date()), Decimal('300.00'))
        self.assertEqual(self.total('reembolsos', VIERNES.date()), Decimal('500.00'))
        self.assertEqual(balances(empresa=self.empresa)['MXN'].reembolsos, Decimal('800.00'))

    def test_corregir_hacia_abajo_es_una_fila_negativa_el_dia_de_la_correccion(self):
        reserva = crear_reserva(
            self.empresa, monto_transferencia=Decimal('5000.00'), transferencia_registrada_en=LUNES,
        )

        reserva = recargar(reserva)
        reserva.monto_transferencia = Decimal('500.00')
        with en(VIERNES):
            reserva.save()

        self.assertEqual(self.total('transferencia', LUNES.date()), Decimal('5000.00'))
        self.assertEqual(self.total('transferencia', VIERNES.date()), Decimal('-4500.00'))
        self.assertEqual(balances(empresa=self.empresa)['MXN'].transferencia, Decimal('500.00'))

    def test_guardar_sin_cambiar_el_monto_no_duplica_filas(self):
        reserva = crear_reserva(self.empresa, monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=LUNES)
        reserva = recargar(reserva)
        reserva.nombre_cliente = 'Otro nombre'
        reserva.save()
        reserva.save()

        self.assertEqual(MovimientoDinero.objects.filter(reserva=reserva).count(), 1)

    def test_reserva_anterior_al_libro_se_lee_de_su_columna_y_recibe_su_fila_base(self):
        reserva = crear_reserva(self.empresa)
        # Dinero ya registrado antes de que existiera el libro: columnas y sello, sin filas.
        Reserva.objects.filter(pk=reserva.pk).update(
            monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=LUNES,
        )
        self.assertEqual(MovimientoDinero.objects.filter(reserva=reserva).count(), 0)
        self.assertEqual(self.total('efectivo', LUNES.date()), Decimal('500.00'))

        reserva = recargar(reserva)
        reserva.monto_efectivo = Decimal('1200.00')
        with en(VIERNES):
            reserva.save()

        self.assertEqual(MovimientoDinero.objects.filter(reserva=reserva, concepto='efectivo').count(), 2)
        self.assertEqual(self.total('efectivo', LUNES.date()), Decimal('500.00'))
        self.assertEqual(self.total('efectivo', VIERNES.date()), Decimal('700.00'))

    def test_quitar_el_efectivo_de_una_reserva_anterior_no_borra_su_historia(self):
        reserva = crear_reserva(self.empresa)
        Reserva.objects.filter(pk=reserva.pk).update(
            monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=LUNES,
        )

        reserva = recargar(reserva)
        reserva.monto_efectivo = Decimal('0.00')
        reserva.efectivo_cobrado_en = None  # lo que hace el admin al quitar el monto
        with en(VIERNES):
            reserva.save()

        self.assertEqual(self.total('efectivo', LUNES.date()), Decimal('500.00'))
        self.assertEqual(self.total('efectivo', VIERNES.date()), Decimal('-500.00'))
        self.assertEqual(balances(empresa=self.empresa)['MXN'].efectivo, Decimal('0.00'))

    def test_por_dia_y_detalle_cuadran_con_el_balance(self):
        reserva = crear_reserva(self.empresa, monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=LUNES)
        reserva = recargar(reserva)
        reserva.monto_efectivo = Decimal('1200.00')
        with en(VIERNES):
            reserva.save()

        dias = {
            dia: por_moneda['MXN'].efectivo
            for dia, por_moneda in balances_por_dia(LUNES.date(), VIERNES.date(), empresa=self.empresa)
        }
        self.assertEqual(dias, {LUNES.date(): Decimal('500.00'), VIERNES.date(): Decimal('700.00')})

        filas = movimientos(concepto='efectivo', moneda='MXN', empresa=self.empresa)
        self.assertEqual(sorted(f.monto for f in filas), [Decimal('500.00'), Decimal('700.00')])
        self.assertEqual(totales_de_movimientos(filas, 'efectivo', 'MXN')['MXN'], Decimal('1200.00'))

    def test_las_filas_llevan_la_empresa_de_la_reserva(self):
        reserva = crear_reserva(self.empresa, monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=LUNES)
        fila = MovimientoDinero.objects.get(reserva=reserva)
        self.assertEqual(fila.empresa_id, self.empresa.pk)
        self.assertEqual(fila.fecha, LUNES)
