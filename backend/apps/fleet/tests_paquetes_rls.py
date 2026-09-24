"""Verificación de las políticas RLS para Paquete y PaqueteServicio contra Postgres (Pieza 5).

Solo aplica en Postgres -- sqlite no tiene RLS. `skipUnless` salta la suite en local.
"""
from decimal import Decimal
from unittest import skipUnless

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class CatalogoPaqueteDeDosEmpresasRlsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede CR', slug='sede-cr-test')
            self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca CR', slug='pesca-cr')
            self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp CR', slug='transp-cr')
            s_pesca = Servicio.objects.create(
                empresa=self.pesca, nombre='Pesca', slug='pesca-cr-s', tipo_servicio='pesca',
                precio_base=Decimal('4000.00'),
            )
            s_transp = Servicio.objects.create(
                empresa=self.transp, nombre='Traslado', slug='traslado-cr-s', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Cruza', slug='cruza-cr',
                precio_ancla=Decimal('9000.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=1)
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_transp, orden=2, personas_incluidas=3)

    def test_el_catalogo_trae_los_componentes_de_las_dos_empresas(self):
        datos = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/cruza-cr/').json()
        self.assertTrue(datos['es_cruza_empresa'])
        empresas = {c['servicio']['empresa_slug'] for c in datos['servicios_asociados']}
        self.assertEqual(empresas, {'pesca-cr', 'transp-cr'})
        traslado = next(c for c in datos['servicios_asociados'] if c['servicio']['slug'] == 'traslado-cr-s')
        self.assertEqual(traslado['personas_incluidas'], 3)

    def test_la_lista_del_catalogo_tambien(self):
        lista = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/').json()
        paquete = next(p for p in lista if p['slug'] == 'cruza-cr')
        self.assertEqual(len(paquete['servicios_asociados']), 2)


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class PaquetesRLSTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='Sede RLS Paquetes', slug='sede-rls-paquetes')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='emp-a-rls-paq')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='emp-b-rls-paq')

        with scope.con_empresa(self.empresa_a):
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
        with scope.como_operador_plataforma():
            self.assertEqual(Paquete.objects.count(), 2)
