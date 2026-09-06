"""Pruebas de integración para la vinculación de Paquete en Reserva (Pieza 5)."""

from datetime import date, time
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.testing import OperadorTestCase

from apps.bookings.models import Reserva
from apps.fleet.models import Paquete, Servicio
from apps.tenancy.models import Empresa, Sede


class ReservaPaqueteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa_lider = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Líder Test', slug='empresa-lider-test'
        )
        self.empresa_otra = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Otra Test', slug='empresa-otra-test'
        )

        self.servicio = Servicio.objects.create(
            empresa=self.empresa_lider,
            nombre='Pesca Paquete',
            slug='pesca-paquete',
            tipo_servicio='pesca',
            precio_base=Decimal('5000.00'),
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa_lider,
            nombre='Paquete Todo Incluido',
            slug='paquete-todo-incluido',
            precio_ancla=Decimal('8000.00'),
        )

    def test_crear_reserva_con_paquete_valido(self):
        reserva = Reserva(
            fecha=date(2026, 10, 15),
            hora=time(6, 0),
            numero_personas=3,
            empresa=self.empresa_lider,
            servicio=self.servicio,
            paquete=self.paquete,
            nombre_cliente='Juan Pérez',
            telefono_cliente='+526121234567',
            correo_cliente='juan@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        reserva.clean()
        reserva.save()

        self.assertEqual(reserva.paquete, self.paquete)
        self.assertIn(reserva, self.paquete.reservas.all())

    def test_reserva_falla_si_empresa_no_es_empresa_lider(self):
        reserva = Reserva(
            fecha=date(2026, 10, 15),
            hora=time(6, 0),
            numero_personas=3,
            empresa=self.empresa_otra,  # Distinta a empresa_lider del paquete
            paquete=self.paquete,
            nombre_cliente='Juan Pérez',
            telefono_cliente='+526121234567',
            correo_cliente='juan@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        with self.assertRaises(ValidationError) as ctx:
            reserva.clean()
        self.assertIn('paquete', ctx.exception.message_dict)

    def test_reserva_sin_paquete_sigue_siendo_valida(self):
        reserva = Reserva(
            fecha=date(2026, 10, 15),
            hora=time(6, 0),
            numero_personas=3,
            empresa=self.empresa_lider,
            servicio=self.servicio,
            paquete=None,
            nombre_cliente='Juan Pérez',
            telefono_cliente='+526121234567',
            correo_cliente='juan@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        reserva.clean()
        reserva.save()
        self.assertIsNone(reserva.paquete)

    def test_borrado_de_paquete_set_null_en_reserva(self):
        reserva = Reserva.objects.create(
            fecha=date(2026, 10, 15),
            hora=time(6, 0),
            numero_personas=3,
            empresa=self.empresa_lider,
            paquete=self.paquete,
            nombre_cliente='Juan Pérez',
            telefono_cliente='+526121234567',
            correo_cliente='juan@example.com',
            canal_origen=Reserva.CanalOrigen.WHATSAPP,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        paquete_pk = self.paquete.pk
        self.paquete.delete()

        reserva.refresh_from_db()
        self.assertIsNone(reserva.paquete)
