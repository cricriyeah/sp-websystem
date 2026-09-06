"""Verificación de las políticas RLS para Paquete y PaqueteServicio contra Postgres (Pieza 5).

Solo aplica en Postgres -- sqlite no tiene RLS. `skipUnless` salta la suite en local.
"""
from decimal import Decimal
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class PaquetesRLSTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='Sede RLS Paquetes', slug='sede-rls-paquetes')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='emp-a-rls-paq')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='emp-b-rls-paq')

        self.servicio_a = Servicio.objects.create(
            empresa=self.empresa_a,
            nombre='Pesca A',
            slug='pesca-a',
            tipo_servicio='pesca',
            precio_base=Decimal('5000.00'),
        )

    def test_aislamiento_paquetes_entre_empresas(self):
        with scope.con_empresa(self.empresa_a):
            paq_a = Paquete.objects.create(
                sede=self.empresa_a.sede,
                empresa_lider=self.empresa_a,
                nombre='Paquete Exclusivo A',
                slug='paquete-a',
                precio_ancla=Decimal('7000.00'),
            )
            PaqueteServicio.objects.create(
                paquete=paq_a,
                servicio=self.servicio_a,
                orden=1,
            )

        with scope.con_empresa(self.empresa_b):
            # Empresa B no debe ver los paquetes liderados por Empresa A
            self.assertEqual(Paquete.objects.count(), 0)
            self.assertEqual(PaqueteServicio.objects.count(), 0)

            # Empresa B crea su propio paquete
            paq_b = Paquete.objects.create(
                sede=self.empresa_b.sede,
                empresa_lider=self.empresa_b,
                nombre='Paquete Exclusivo B',
                slug='paquete-b',
                precio_ancla=Decimal('8000.00'),
            )
            self.assertEqual(Paquete.objects.count(), 1)
            self.assertEqual(Paquete.objects.first().slug, 'paquete-b')

        # Operador de plataforma ve ambos
        with scope.con_operador_plataforma():
            self.assertEqual(Paquete.objects.count(), 2)
