"""«Registrar liquidacion en efectivo»: saldar lo que un cliente debe en efectivo.

La duena pregunto si habia forma de declarar o saldar esa deuda. La accion ya
existia en la lista pero sin guardas (corria sobre cualquier estado, sin
confirmar y leyendo el saldo de una copia que pudo cambiar) y no se encontraba
desde la reserva.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.finance.services import balances
from apps.testing import EmpresaTestCase

from .cobros import liquidar_saldo_en_efectivo
from .models import Reserva
from .tests import crear_reserva

ACCION = 'registrar_liquidacion_en_efectivo'


class LiquidacionConGuardasTests(EmpresaTestCase):
    def setUp(self):
        self.jefa = self.crear_jefe()
        self.client.force_login(self.jefa)
        self.lista = reverse('admin:bookings_reserva_changelist')

    def reserva(self, estado=Reserva.Estado.PAGADA, nombre='Ana Ruiz', **campos):
        datos = dict(
            forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('4500.00'),
            monto_pagado=Decimal('1350.00'), pagada_en=timezone.now(), nombre_cliente=nombre,
        )
        datos.update(campos)
        return crear_reserva(self.empresa, estado=estado, **datos)

    def pedir(self, reservas, confirmar=True):
        datos = {'action': ACCION, '_selected_action': [str(r.pk) for r in reservas]}
        if confirmar:
            datos['confirmar_liquidacion'] = 'si'
        return self.client.post(self.lista, datos)

    # --- confirmacion ---------------------------------------------------------

    def test_sin_confirmar_solo_muestra_lo_que_se_va_a_anotar(self):
        reserva = self.reserva(nombre='Beto Lopez')

        respuesta = self.pedir([reserva], confirmar=False)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Beto Lopez')
        self.assertContains(respuesta, '3150.00 MXN')
        self.assertContains(respuesta, 'name="confirmar_liquidacion"')
        self.assertContains(respuesta, 'name="csrfmiddlewaretoken"')
        reserva.refresh_from_db()
        self.assertIsNone(reserva.monto_efectivo)
        self.assertIsNone(reserva.efectivo_cobrado_en)

    def test_confirmada_salda_y_deja_constancia_de_quien_y_cuando(self):
        reserva = self.reserva()

        respuesta = self.pedir([reserva])

        self.assertEqual(respuesta.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))
        self.assertEqual(reserva.saldo_pendiente, Decimal('0.00'))
        self.assertEqual(reserva.efectivo_cobrado_por, self.jefa)
        self.assertIsNotNone(reserva.efectivo_cobrado_en)
        entrada = LogEntry.objects.filter(object_id=str(reserva.pk), user=self.jefa).latest('action_time')
        self.assertIn('3150', entrada.change_message)

    def test_lo_saldado_entra_a_finanzas_como_efectivo(self):
        reserva = self.reserva()
        self.pedir([reserva])

        hoy = timezone.localdate()
        balance = balances(hoy, hoy, empresa=self.empresa)['MXN']
        self.assertEqual(balance.efectivo, Decimal('3150.00'))

    # --- guardas de estado --------------------------------------------------------

    def test_una_asignada_con_saldo_si_se_puede_saldar(self):
        reserva = self.reserva(estado=Reserva.Estado.ASIGNADA, embarcacion=None)
        Reserva.objects.filter(pk=reserva.pk).update(estado=Reserva.Estado.ASIGNADA)

        self.pedir([reserva])

        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))

    def test_no_salda_canceladas_pendientes_ni_reembolsadas(self):
        cancelada = self.reserva(estado=Reserva.Estado.CANCELADA, nombre='Cancelada',
                                 monto_reembolsado=Decimal('1350.00'), reembolsada=True)
        pendiente = self.reserva(estado=Reserva.Estado.PENDIENTE_PAGO, nombre='Pendiente',
                                 monto_pagado=None, forma_pago='')
        reembolsada = self.reserva(nombre='Reembolsada', reembolsada=True)

        respuesta = self.pedir([cancelada, pendiente, reembolsada])

        self.assertEqual(respuesta.status_code, 302)
        for reserva in (cancelada, pendiente, reembolsada):
            reserva.refresh_from_db()
            self.assertIsNone(reserva.monto_efectivo, reserva.nombre_cliente)
            self.assertIsNone(reserva.efectivo_cobrado_en, reserva.nombre_cliente)

    def test_la_confirmacion_cuenta_solo_las_que_si_se_saldan(self):
        buena = self.reserva(nombre='Buena')
        cancelada = self.reserva(estado=Reserva.Estado.CANCELADA, nombre='Cancelada',
                                 monto_reembolsado=Decimal('1350.00'))

        respuesta = self.pedir([buena, cancelada], confirmar=False)

        self.assertContains(respuesta, 'Buena')
        self.assertNotContains(respuesta, 'Cancelada &middot;')
        self.assertEqual(respuesta.context['cantidad'], 1)
        self.assertEqual(respuesta.context['omitidas'], 1)

    def test_el_aviso_dice_cuantas_se_saldaron_y_cuantas_no(self):
        buena = self.reserva(nombre='Buena')
        cancelada = self.reserva(estado=Reserva.Estado.CANCELADA, nombre='Cancelada',
                                 monto_reembolsado=Decimal('1350.00'))

        respuesta = self.client.post(self.lista, {
            'action': ACCION, '_selected_action': [str(buena.pk), str(cancelada.pk)],
            'confirmar_liquidacion': 'si',
        }, follow=True)

        self.assertContains(respuesta, '1 reserva(s) liquidada(s).')
        self.assertContains(respuesta, '1 se omitieron')

    # --- nunca de mas ----------------------------------------------------------------

    def test_repetir_el_clic_no_cobra_dos_veces(self):
        reserva = self.reserva()

        self.pedir([reserva])
        self.pedir([reserva])

        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))

    def test_si_otro_ya_salda_entre_la_pantalla_y_la_confirmacion_no_suma_de_mas(self):
        """El saldo se vuelve a leer ya con la fila bloqueada: una copia vieja
        (la de la pantalla de confirmacion) no puede mandar sobre la base."""
        reserva = self.reserva()
        copia_vieja = Reserva.objects.get(pk=reserva.pk)
        self.assertEqual(copia_vieja.saldo_pendiente, Decimal('3150.00'))
        self.pedir([reserva])

        monto = liquidar_saldo_en_efectivo(copia_vieja.pk, self.jefa)

        self.assertIsNone(monto)
        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))

    def test_con_efectivo_previo_solo_cobra_lo_que_falta(self):
        reserva = self.reserva(monto_efectivo=Decimal('1000.00'))

        self.pedir([reserva])

        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))

    def test_no_pisa_la_fecha_del_primer_efectivo(self):
        primera = timezone.now() - timedelta(days=3)
        reserva = self.reserva(monto_efectivo=Decimal('1000.00'),
                               efectivo_cobrado_en=primera, efectivo_cobrado_por=self.jefa)

        self.pedir([reserva])

        reserva.refresh_from_db()
        self.assertEqual(reserva.efectivo_cobrado_en, primera)

    def test_una_reserva_pagada_al_100_no_debe_nada(self):
        reserva = self.reserva(forma_pago=Reserva.FormaPago.COMPLETO,
                               monto_pagado=Decimal('4500.00'))

        self.pedir([reserva])

        reserva.refresh_from_db()
        self.assertIsNone(reserva.monto_efectivo)

    # --- permisos -----------------------------------------------------------------------

    def test_quien_solo_puede_ver_no_puede_saldar(self):
        reserva = self.reserva()
        solo_lectura = self.crear_vendedora(username='solo-lee', permisos=[])
        solo_lectura.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(solo_lectura)

        self.pedir([reserva])

        reserva.refresh_from_db()
        self.assertIsNone(reserva.monto_efectivo)


class BotonDeSaldarEnLaReservaTests(EmpresaTestCase):
    """El boton vive en el resumen de la reserva: no hay que ir a la lista ni
    acordarse de la accion."""

    def setUp(self):
        self.jefa = self.crear_jefe()
        self.client.force_login(self.jefa)

    def abrir(self, reserva):
        return self.client.get(reverse('admin:bookings_reserva_change', args=[reserva.pk]))

    def con_saldo(self, **campos):
        datos = dict(forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('4500.00'),
                     monto_pagado=Decimal('1350.00'))
        datos.update(campos)
        return crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA, **datos)

    def test_la_reserva_con_saldo_ofrece_cobrarlo(self):
        reserva = self.con_saldo()

        respuesta = self.abrir(reserva)

        self.assertContains(respuesta, 'Cobrar saldo en efectivo')
        self.assertContains(respuesta, f'name="action" value="{ACCION}"')
        self.assertContains(respuesta, f'name="_selected_action" value="{reserva.pk}"')
        self.assertContains(respuesta, '3,150 MXN')

    def test_el_boton_lleva_a_la_pantalla_de_confirmacion(self):
        reserva = self.con_saldo()

        respuesta = self.client.post(reverse('admin:bookings_reserva_changelist'), {
            'action': ACCION, '_selected_action': [str(reserva.pk)],
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'confirmar_liquidacion')
        reserva.refresh_from_db()
        self.assertIsNone(reserva.monto_efectivo)

    def test_sin_saldo_no_hay_boton(self):
        reserva = self.con_saldo(forma_pago=Reserva.FormaPago.COMPLETO,
                                 monto_pagado=Decimal('4500.00'))

        self.assertNotContains(self.abrir(reserva), 'Cobrar saldo en efectivo')

    def test_una_cancelada_no_ofrece_cobrar(self):
        reserva = self.con_saldo()
        Reserva.objects.filter(pk=reserva.pk).update(
            estado=Reserva.Estado.CANCELADA, reembolsada=True, monto_reembolsado=Decimal('1350.00'))

        self.assertNotContains(self.abrir(reserva), 'Cobrar saldo en efectivo')

    def test_quien_solo_puede_ver_no_ve_el_boton(self):
        reserva = self.con_saldo()
        solo_lectura = self.crear_vendedora(username='solo-lee', permisos=[])
        solo_lectura.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(solo_lectura)

        self.assertNotContains(self.abrir(reserva), 'Cobrar saldo en efectivo')
