"""Pruebas para modelos de selección de paquete en checkout (Pieza 5)."""

from datetime import date, time
from decimal import Decimal
from unittest import skipUnless
from django.db import DatabaseError, connection, transaction
from django.db.utils import IntegrityError
from django.test import TransactionTestCase

from apps.testing import OperadorTestCase
from apps.bookings.models import (
    Reserva,
    ReservaPaqueteComponente,
    ReservaPersonalizacion,
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
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_pesca, orden=1)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_snack, orden=2)

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

    def test_crear_personalizacion_paquete(self):
        pers = ReservaPersonalizacion.objects.create(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            cantidad=2,
        )
        self.assertEqual(self.reserva.personalizaciones_seleccionadas.count(), 1)
        self.assertEqual(self.reserva.personalizaciones_seleccionadas.first(), pers)

    def test_unicidad_personalizacion_por_reserva(self):
        ReservaPersonalizacion.objects.create(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            cantidad=1,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReservaPersonalizacion.objects.create(
                    reserva=self.reserva,
                    servicio_personalizacion=self.sp,
                    cantidad=3,
                )

    def test_crear_componente_paquete(self):
        comp = ReservaPaqueteComponente.objects.create(
            reserva=self.reserva,
            servicio=self.servicio_pesca,
            empresa=self.empresa,
        )
        self.assertEqual(comp.estado_cupo, ReservaPaqueteComponente.EstadoCupo.OK)
        self.assertEqual(self.reserva.componentes.count(), 1)
        self.assertEqual(self.reserva.componentes.first(), comp)
        self.assertIn("Componente", str(comp))

    def test_unicidad_componente_por_reserva_y_servicio(self):
        ReservaPaqueteComponente.objects.create(
            reserva=self.reserva,
            servicio=self.servicio_pesca,
            empresa=self.empresa,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReservaPaqueteComponente.objects.create(
                    reserva=self.reserva,
                    servicio=self.servicio_pesca,
                    empresa=self.empresa,
                )


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class ReservaCheckoutPaqueteRLSTests(TransactionTestCase):
    """Pruebas de aislamiento RLS en PostgreSQL para las selecciones de paquete."""

    def setUp(self):
        # Todo el fixture se arma con alcance de operador. Las pruebas son las
        # únicas que cambian a un tenant concreto, para que cada lectura e
        # INSERT demuestre la política y no dependa del orden del setUp.
        with scope.como_operador_plataforma():
            sede = Sede.objects.create(nombre='Sede RLS Checkout', slug='sede-rls-checkout')
            self.empresa_a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='empresa-a')
            self.empresa_b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='empresa-b')

            srv_a = Servicio.objects.create(
                empresa=self.empresa_a, nombre='Srv A', slug='srv-a', precio_base=Decimal('100'),
            )
            pers_a = Personalizacion.objects.create(empresa=self.empresa_a, nombre='Pers A')
            self.sp_a = ServicioPersonalizacion.objects.create(servicio=srv_a, personalizacion=pers_a, precio=Decimal('50'))
            self.paquete_a = Paquete.objects.create(sede=sede, empresa_lider=self.empresa_a, nombre='Pack A', slug='pack-a', precio_ancla=Decimal('500'))
            self.reserva_a = Reserva.objects.create(
                empresa=self.empresa_a, paquete=self.paquete_a, fecha=date(2026, 12, 1), hora=time(7, 0),
                numero_personas=2, nombre_cliente='A', telefono_cliente='111', correo_cliente='a@a.com',
                deslinde_aceptado=True,
            )
            self.pers_a_row = ReservaPersonalizacion.objects.create(reserva=self.reserva_a, servicio_personalizacion=self.sp_a, cantidad=1)
            self.comp_a = ReservaPaqueteComponente.objects.create(reserva=self.reserva_a, servicio=srv_a, empresa=self.empresa_a)

            srv_b = Servicio.objects.create(empresa=self.empresa_b, nombre='Srv B', slug='srv-b', precio_base=Decimal('100'))
            self.paquete_b = Paquete.objects.create(sede=sede, empresa_lider=self.empresa_b, nombre='Pack B', slug='pack-b', precio_ancla=Decimal('500'))
            self.reserva_b = Reserva.objects.create(
                empresa=self.empresa_b, paquete=self.paquete_b, fecha=date(2026, 12, 1), hora=time(7, 0),
                numero_personas=2, nombre_cliente='B', telefono_cliente='222', correo_cliente='b@b.com',
                deslinde_aceptado=True,
            )

            servicio_directo_a = Servicio.objects.create(
                empresa=self.empresa_a, nombre='Directo A', slug='directo-a',
                tipo_servicio='otro', estrategia_cupo='bajo_demanda',
                precio_base=Decimal('100'),
            )
            personalizacion_directa_a = Personalizacion.objects.create(
                empresa=self.empresa_a, nombre='Directa A',
            )
            self.sp_directa_a = ServicioPersonalizacion.objects.create(
                servicio=servicio_directo_a,
                personalizacion=personalizacion_directa_a,
                precio=Decimal('25'),
            )
            reserva_directa_a = Reserva.objects.create(
                empresa=self.empresa_a, servicio=servicio_directo_a,
                fecha=date(2026, 12, 2), hora=time(8, 0), numero_personas=2,
                nombre_cliente='Directo A', telefono_cliente='111',
                correo_cliente='directo-a@example.com', deslinde_aceptado=True,
            )
            self.fila_directa_a = ReservaPersonalizacion.objects.create(
                reserva=reserva_directa_a,
                servicio_personalizacion=self.sp_directa_a,
            )

            servicio_directo_b = Servicio.objects.create(
                empresa=self.empresa_b, nombre='Directo B', slug='directo-b',
                tipo_servicio='otro', estrategia_cupo='bajo_demanda',
                precio_base=Decimal('100'),
            )
            personalizacion_directa_b = Personalizacion.objects.create(
                empresa=self.empresa_b, nombre='Directa B',
            )
            self.sp_directa_b = ServicioPersonalizacion.objects.create(
                servicio=servicio_directo_b,
                personalizacion=personalizacion_directa_b,
                precio=Decimal('30'),
            )
            reserva_directa_b = Reserva.objects.create(
                empresa=self.empresa_b, servicio=servicio_directo_b,
                fecha=date(2026, 12, 2), hora=time(8, 0), numero_personas=2,
                nombre_cliente='Directo B', telefono_cliente='222',
                correo_cliente='directo-b@example.com', deslinde_aceptado=True,
            )
            self.fila_directa_b = ReservaPersonalizacion.objects.create(
                reserva=reserva_directa_b,
                servicio_personalizacion=self.sp_directa_b,
            )

    def test_empresa_b_no_ve_personalizaciones_de_empresa_a(self):
        with scope.con_empresa(self.empresa_b):
            self.assertEqual(
                ReservaPersonalizacion.objects.filter(reserva__paquete__isnull=False).count(),
                0,
            )
            self.assertEqual(ReservaPaqueteComponente.objects.count(), 0)

    def test_empresa_a_ve_sus_propias_filas(self):
        with scope.con_empresa(self.empresa_a):
            self.assertEqual(
                ReservaPersonalizacion.objects.filter(reserva__paquete__isnull=False).count(),
                1,
            )
            self.assertEqual(ReservaPaqueteComponente.objects.count(), 1)
            self.assertEqual(
                ReservaPersonalizacion.objects.get(reserva__paquete__isnull=False),
                self.pers_a_row,
            )
            self.assertEqual(ReservaPaqueteComponente.objects.first(), self.comp_a)

    def test_operador_ve_todas_las_filas(self):
        with scope.como_operador_plataforma():
            self.assertEqual(ReservaPersonalizacion.objects.count(), 3)
            self.assertEqual(ReservaPaqueteComponente.objects.count(), 1)

    def test_servicio_directo_aisla_lectura_e_insert_cruzado(self):
        with scope.con_empresa(self.empresa_b):
            self.assertFalse(
                ReservaPersonalizacion.objects.filter(pk=self.fila_directa_a.pk).exists()
            )
            self.assertEqual(
                list(ReservaPersonalizacion.objects.values_list('pk', flat=True)),
                [self.fila_directa_b.pk],
            )

            # El assert captura el error fuera del savepoint: al salir del
            # atomic interno la conexión vuelve a quedar utilizable.
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    ReservaPersonalizacion.objects.create(
                        reserva_id=self.fila_directa_a.reserva_id,
                        servicio_personalizacion_id=self.sp_directa_a.pk,
                    )

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user'
            )
            self.assertEqual(cursor.fetchone(), (False, False))
            cursor.execute(
                'SELECT policyname FROM pg_policies WHERE tablename=%s',
                ['bookings_reservapersonalizacion'],
            )
            self.assertIn(('tenancy_alcance',), cursor.fetchall())
