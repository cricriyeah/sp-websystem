"""Pruebas para modelos de selección de paquete en checkout (Pieza 5)."""

from datetime import date, time
from decimal import Decimal
from unittest import skipUnless
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.test import TransactionTestCase

from apps.testing import OperadorTestCase
from apps.bookings.models import (
    Reserva,
    ReservaPaquetePersonalizacion,
    ReservaPaqueteServicioRemovido,
)
from apps.fleet.models import Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class ReservaCheckoutPaqueteModelTests(OperadorTestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Paquete', slug='sede-paquete')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Paquete', slug='empresa-paquete')
        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca', tipo_servicio='pesca',
            precio_base=Decimal('5000.00'),
        )
        self.servicio_snack = Servicio.objects.create(
            empresa=self.empresa, nombre='Snack', slug='snack', tipo_servicio='otro',
            precio_base=Decimal('1000.00'),
        )
        self.personalizacion = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Bebidas',
        )
        self.sp = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=self.personalizacion, precio=Decimal('200.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Pack', slug='pack', precio_ancla=Decimal('6000.00'),
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_pesca, orden=1, removible=False)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_snack, orden=2, removible=True)

        self.reserva = Reserva.objects.create(
            empresa=self.empresa,
            paquete=self.paquete,
            fecha=date(2026, 11, 1),
            hora=time(7, 0),
            numero_personas=2,
            nombre_cliente='Cliente',
            telefono_cliente='1234567890',
            correo_cliente='c@test.com',
            moneda='MXN',
            deslinde_aceptado=True,
        )

    def test_crear_servicio_removido_y_personalizacion(self):
        removido = ReservaPaqueteServicioRemovido.objects.create(
            reserva=self.reserva,
            servicio=self.servicio_snack,
        )
        pers = ReservaPaquetePersonalizacion.objects.create(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            cantidad=2,
        )
        self.assertEqual(self.reserva.servicios_removidos.count(), 1)
        self.assertEqual(self.reserva.paquete_personalizaciones.count(), 1)
        self.assertEqual(self.reserva.servicios_removidos.first(), removido)
        self.assertEqual(self.reserva.paquete_personalizaciones.first(), pers)

    def test_unicidad_servicio_removido_por_reserva(self):
        ReservaPaqueteServicioRemovido.objects.create(
            reserva=self.reserva,
            servicio=self.servicio_snack,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReservaPaqueteServicioRemovido.objects.create(
                    reserva=self.reserva,
                    servicio=self.servicio_snack,
                )

    def test_unicidad_personalizacion_por_reserva(self):
        ReservaPaquetePersonalizacion.objects.create(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            cantidad=1,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReservaPaquetePersonalizacion.objects.create(
                    reserva=self.reserva,
                    servicio_personalizacion=self.sp,
                    cantidad=3,
                )


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class ReservaCheckoutPaqueteRLSTests(TransactionTestCase):
    """Pruebas de aislamiento RLS en PostgreSQL para las selecciones de paquete."""

    def setUp(self):
        sede = Sede.objects.create(nombre='Sede RLS Checkout', slug='sede-rls-checkout')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='empresa-b')

        with scope.con_empresa(self.empresa_a):
            srv_a = Servicio.objects.create(empresa=self.empresa_a, nombre='Srv A', slug='srv-a', precio_base=Decimal('100'))
            pers_a = Personalizacion.objects.create(empresa=self.empresa_a, nombre='Pers A')
            self.sp_a = ServicioPersonalizacion.objects.create(servicio=srv_a, personalizacion=pers_a, precio=Decimal('50'))
            self.paquete_a = Paquete.objects.create(sede=sede, empresa_lider=self.empresa_a, nombre='Pack A', slug='pack-a', precio_ancla=Decimal('500'))
            self.reserva_a = Reserva.objects.create(
                empresa=self.empresa_a, paquete=self.paquete_a, fecha=date(2026, 12, 1), hora=time(7, 0),
                numero_personas=2, nombre_cliente='A', telefono_cliente='111', correo_cliente='a@a.com',
                deslinde_aceptado=True,
            )
            self.rem_a = ReservaPaqueteServicioRemovido.objects.create(reserva=self.reserva_a, servicio=srv_a)
            self.pers_a_row = ReservaPaquetePersonalizacion.objects.create(reserva=self.reserva_a, servicio_personalizacion=self.sp_a, cantidad=1)

        with scope.con_empresa(self.empresa_b):
            srv_b = Servicio.objects.create(empresa=self.empresa_b, nombre='Srv B', slug='srv-b', precio_base=Decimal('100'))
            self.paquete_b = Paquete.objects.create(sede=sede, empresa_lider=self.empresa_b, nombre='Pack B', slug='pack-b', precio_ancla=Decimal('500'))
            self.reserva_b = Reserva.objects.create(
                empresa=self.empresa_b, paquete=self.paquete_b, fecha=date(2026, 12, 1), hora=time(7, 0),
                numero_personas=2, nombre_cliente='B', telefono_cliente='222', correo_cliente='b@b.com',
                deslinde_aceptado=True,
            )

    def test_empresa_b_no_ve_removidos_ni_personalizaciones_de_empresa_a(self):
        with scope.con_empresa(self.empresa_b):
            self.assertEqual(ReservaPaqueteServicioRemovido.objects.count(), 0)
            self.assertEqual(ReservaPaquetePersonalizacion.objects.count(), 0)

    def test_empresa_a_ve_sus_propias_filas(self):
        with scope.con_empresa(self.empresa_a):
            self.assertEqual(ReservaPaqueteServicioRemovido.objects.count(), 1)
            self.assertEqual(ReservaPaquetePersonalizacion.objects.count(), 1)
            self.assertEqual(ReservaPaqueteServicioRemovido.objects.first(), self.rem_a)
            self.assertEqual(ReservaPaquetePersonalizacion.objects.first(), self.pers_a_row)

    def test_operador_ve_todas_las_filas(self):
        with scope.como_operador_plataforma():
            self.assertEqual(ReservaPaqueteServicioRemovido.objects.count(), 1)
            self.assertEqual(ReservaPaquetePersonalizacion.objects.count(), 1)
