"""Borrar una reserva con lo que cuelga de ella: habitaciones ocupadas, componentes de paquete y tramos de traslado.

Antes el aviso era «no tienes permiso para eliminar...» aunque el jefe pudiera borrar reservas, porque Django
exige permiso de borrar sobre cada tipo de lo que se borra en cascada.
"""
from datetime import date, time, timedelta
from types import SimpleNamespace

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.urls import reverse

from apps.bookings.admin import (
    ReservaOcupacionAdmin, ReservaPaqueteComponenteAdmin, ViajeTransporteAdmin,
)
from apps.bookings.models import Reserva, ReservaPaqueteComponente
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca


class BorrarReservaTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(self.empresa)
        self.jefe = self.crear_jefe()
        self.client.force_login(self.jefe)

    def reserva_con_componente(self):
        reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.servicio, fecha=date.today() + timedelta(days=20), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', estado=Reserva.Estado.PENDIENTE_PAGO, canal_origen='web',
            deslinde_aceptado=True, moneda='MXN',
        )
        ReservaPaqueteComponente.objects.create(reserva=reserva, servicio=self.servicio, empresa=self.empresa)
        return reserva

    def test_la_confirmacion_de_borrado_no_dice_que_falta_permiso(self):
        reserva = self.reserva_con_componente()

        respuesta = self.client.get(reverse('admin:bookings_reserva_delete', args=[reserva.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['perms_lacking'], set())
        self.assertEqual(respuesta.context['protected'], [])

    def test_confirmar_el_borrado_se_lleva_los_componentes(self):
        reserva = self.reserva_con_componente()

        respuesta = self.client.post(reverse('admin:bookings_reserva_delete', args=[reserva.pk]), {'post': 'yes'})

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Reserva.objects.filter(pk=reserva.pk).exists())
        self.assertFalse(ReservaPaqueteComponente.objects.filter(reserva_id=reserva.pk).exists())


class PermisoDeBorrarLoQueCuelgaTests(EmpresaTestCase):
    """El permiso vale solo mientras se borra la reserva: sueltos, esos registros no se borran."""

    def pedir(self, url_name, usuario):
        return SimpleNamespace(resolver_match=SimpleNamespace(url_name=url_name), user=usuario)

    def admins(self):
        return [a for a in site._registry.values()
                if type(a) in (ReservaOcupacionAdmin, ReservaPaqueteComponenteAdmin, ViajeTransporteAdmin)]

    def test_con_la_reserva_si_y_sueltos_no(self):
        jefe = self.crear_jefe()
        admins = self.admins()
        self.assertEqual(len(admins), 3)
        for admin in admins:
            nombre = admin.model._meta.model_name
            self.assertTrue(admin.has_delete_permission(self.pedir('bookings_reserva_delete', jefe)), nombre)
            self.assertTrue(admin.has_delete_permission(self.pedir('bookings_reserva_changelist', jefe)), nombre)
            self.assertFalse(admin.has_delete_permission(self.pedir(f'bookings_{nombre}_delete', jefe)), nombre)
            self.assertFalse(admin.has_delete_permission(self.pedir(f'bookings_{nombre}_changelist', jefe)), nombre)

    def test_quien_no_puede_borrar_reservas_tampoco_las_borra_en_cascada(self):
        sin_permiso = User.objects.create_user('sin-permisos', is_staff=True, password='x')
        for admin in self.admins():
            self.assertFalse(admin.has_delete_permission(self.pedir('bookings_reserva_delete', sin_permiso)))
