"""Bajar o cerrar el cupo de un dia no debe impedir repartir los viajes que ya estaban vendidos.

Auditoria 2026-10-23: `Reserva.clean()` volvia a pedirle cupo a una reserva que ya lo ocupaba cada vez
que se guardaba (por ejemplo, al ponerle panga desde «Asignar pangas»). Si el negocio habia bajado el
`CupoDiario` por debajo de lo vendido, el viaje ya vendido se rechazaba a si mismo. El tope frena
ventas NUEVAS; lo ya vendido sigue siendo suyo.
"""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.fleet.models import Embarcacion
from apps.testing import EmpresaTestCase, crear_flota

from .models import CupoDiario, Reserva
from .tests_agenda import datos, viaje


class AsignarViajesYaVendidosTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.dia = date.today() + timedelta(days=5)
        self.vendidos = [
            viaje(self.empresa, fecha=self.dia, nombre_cliente=nombre, numero_personas=2)
            for nombre in ('Cliente Uno', 'Cliente Dos', 'Cliente Tres')
        ]

    def panga(self):
        return Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima__gte=3).first()

    def asignar(self, reserva, panga):
        return self.client.post(self.url, {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1', 'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(reserva.pk), 'form-0-embarcacion': str(panga.pk), 'form-0-capitan': '',
            '_save': 'Guardar',
        })

    def test_con_el_cupo_bajado_por_debajo_de_lo_vendido_se_puede_asignar_panga(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.dia, cupo_maximo=1)

        respuesta = self.asignar(self.vendidos[0], self.panga())

        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['cl'].formset.errors)
        self.vendidos[0].refresh_from_db()
        self.assertEqual(self.vendidos[0].embarcacion_id, self.panga().pk)
        self.assertEqual(self.vendidos[0].estado, Reserva.Estado.ASIGNADA)

    def test_con_el_dia_cerrado_tambien_se_puede_asignar_panga(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.dia, cupo_maximo=0)

        respuesta = self.asignar(self.vendidos[1], self.panga())

        self.assertEqual(respuesta.status_code, 302)
        self.vendidos[1].refresh_from_db()
        self.assertEqual(self.vendidos[1].estado, Reserva.Estado.ASIGNADA)

    def test_una_venta_nueva_ese_dia_sigue_bloqueada(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.dia, cupo_maximo=1)

        nueva = Reserva(**datos(self.empresa, fecha=self.dia, nombre_cliente='Nueva'))

        with self.assertRaises(ValidationError) as ctx:
            nueva.full_clean()
        self.assertIn('No hay cupo disponible', str(ctx.exception.message_dict))

    def test_mover_un_viaje_vendido_a_un_dia_cerrado_sigue_rechazandose(self):
        cerrado = self.dia + timedelta(days=2)
        CupoDiario.objects.create(empresa=self.empresa, fecha=cerrado, cupo_maximo=0)

        reserva = Reserva.objects.get(pk=self.vendidos[0].pk)
        reserva.fecha = cerrado

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('No hay cupo disponible', str(ctx.exception.message_dict))

    def test_agrandar_el_grupo_de_un_viaje_vendido_revalida_el_cupo(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.dia, cupo_maximo=1)

        reserva = Reserva.objects.get(pk=self.vendidos[0].pk)
        reserva.numero_personas = 3

        with self.assertRaises(ValidationError):
            reserva.full_clean()

    def test_editar_otro_dato_de_un_viaje_vendido_no_pide_cupo(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.dia, cupo_maximo=0)

        reserva = Reserva.objects.get(pk=self.vendidos[2].pk)
        reserva.telefono_cliente = '+5216129998877'
        reserva.full_clean()  # no lanza
        reserva.save()
