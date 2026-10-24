"""La columna «Cobro» frente a reembolsos hechos en Stripe.

Antes de este arreglo una reserva cancelada con anticipo seguia diciendo
"Debe 3,150 MXN en efectivo" aunque el cliente ya no iba a venir, y un
reembolso parcial no se veia por ningun lado en la fila.
"""
from decimal import Decimal

from django.contrib import admin

from apps.bookings.models import Reserva
from apps.bookings.tests import crear_reserva
from apps.testing import EmpresaTestCase


class CobroConReembolsosTests(EmpresaTestCase):
    def setUp(self):
        self.model_admin = admin.site._registry[Reserva]

    def cobro(self, **campos):
        reserva = crear_reserva(self.empresa, **campos)
        return str(self.model_admin.cobro(reserva))

    def test_cancelada_con_anticipo_devuelto_no_dice_que_debe(self):
        texto = self.cobro(
            estado=Reserva.Estado.CANCELADA, forma_pago=Reserva.FormaPago.ANTICIPO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
            monto_reembolsado=Decimal('1350.00'), reembolsada=True,
        )

        self.assertNotIn('Debe', texto)
        self.assertEqual(texto, 'Devuelto 1,350 MXN')

    def test_cancelada_sin_haber_cobrado_nada_no_dice_que_hay_descuadre(self):
        texto = self.cobro(
            estado=Reserva.Estado.CANCELADA, precio_total=Decimal('4500.00'),
        )

        self.assertNotIn('Descuadre', texto)
        self.assertNotIn('Debe', texto)
        self.assertEqual(texto, 'Cancelada')

    def test_cancelada_con_devolucion_pendiente_sigue_pidiendo_atencion(self):
        texto = self.cobro(
            estado=Reserva.Estado.CANCELADA, precio_total=Decimal('1200.00'),
            monto_pagado=Decimal('1200.00'),
        )

        self.assertIn('Falta devolver 1,200 MXN', texto)

    def test_reembolso_parcial_de_una_reserva_pagada_se_ve_en_la_fila(self):
        texto = self.cobro(
            estado=Reserva.Estado.PAGADA, forma_pago=Reserva.FormaPago.COMPLETO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('4500.00'),
            monto_reembolsado=Decimal('1000.00'),
        )

        self.assertEqual(texto, 'Pagado · devuelto 1,000 MXN')

    def test_reembolso_parcial_no_inventa_deuda_en_efectivo(self):
        """Por que se devolvio una parte (descuento, un lugar menos) no se sabe:
        el saldo sigue siendo precio contra lo cobrado. Solo se anota lo devuelto."""
        texto = self.cobro(
            estado=Reserva.Estado.PAGADA, forma_pago=Reserva.FormaPago.ANTICIPO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
            monto_reembolsado=Decimal('500.00'),
        )

        self.assertEqual(texto, 'Debe 3,150 MXN en efectivo · devuelto 500 MXN')

    def test_sin_reembolsos_el_texto_no_cambia(self):
        texto = self.cobro(
            estado=Reserva.Estado.PAGADA, forma_pago=Reserva.FormaPago.ANTICIPO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
        )

        self.assertEqual(texto, 'Debe 3,150 MXN en efectivo')
