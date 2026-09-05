"""Pruebas de Row Level Security (RLS) en PostgreSQL para ReservaOcupacion."""

from datetime import date, time
from unittest import skipUnless
from django.db import connection
from django.test import TransactionTestCase

from apps.fleet.models import Recurso
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.bookings.models import Reserva, ReservaOcupacion


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class ReservaOcupacionRLSTests(TransactionTestCase):
    """Pruebas de aislamiento multi-tenant a nivel de base de datos para ReservaOcupacion."""

    def setUp(self):
        sede = Sede.objects.create(nombre='Sede RLS Ocupacion', slug='sede-rls-ocupacion')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Empresa Ocup A', slug='empresa-ocup-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Empresa Ocup B', slug='empresa-ocup-b')

        self.recurso_a = Recurso.objects.create(
            empresa=self.empresa_a,
            nombre='Habitacion A',
            capacidad_maxima=2,
        )
        self.recurso_b = Recurso.objects.create(
            empresa=self.empresa_b,
            nombre='Habitacion B',
            capacidad_maxima=2,
        )

        self.reserva_a = Reserva.objects.create(
            empresa=self.empresa_a,
            fecha=date(2026, 11, 1),
            fecha_salida=date(2026, 11, 5),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Cliente A',
            telefono_cliente='+526121111111',
            correo_cliente='a@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )
        self.reserva_b = Reserva.objects.create(
            empresa=self.empresa_b,
            fecha=date(2026, 11, 1),
            fecha_salida=date(2026, 11, 5),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Cliente B',
            telefono_cliente='+526122222222',
            correo_cliente='b@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )

    def test_aislamiento_reserva_ocupacion_entre_empresas(self):
        """Verifica que una empresa no pueda consultar ocupaciones de otra empresa bajo RLS."""
        with scope.con_empresa(self.empresa_a):
            ReservaOcupacion.objects.create(
                empresa=self.empresa_a,
                reserva=self.reserva_a,
                recurso=self.recurso_a,
                fecha_inicio=date(2026, 11, 1),
                fecha_fin=date(2026, 11, 5),
            )

        with scope.con_empresa(self.empresa_b):
            ReservaOcupacion.objects.create(
                empresa=self.empresa_b,
                reserva=self.reserva_b,
                recurso=self.recurso_b,
                fecha_inicio=date(2026, 11, 1),
                fecha_fin=date(2026, 11, 5),
            )

            # Empresa B solo ve su propia ocupación
            self.assertEqual(ReservaOcupacion.objects.count(), 1)
            self.assertEqual(ReservaOcupacion.objects.first().empresa_id, self.empresa_b.pk)

        # Operador de plataforma ve ambas
        with scope.como_operador_plataforma():
            self.assertEqual(ReservaOcupacion.objects.count(), 2)
