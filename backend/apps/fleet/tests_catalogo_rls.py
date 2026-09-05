"""Verificación de las políticas RLS para modelos de catálogo contra Postgres (Pieza 3).

Solo aplica en Postgres -- sqlite no tiene RLS. `skipUnless` salta la suite en local.
"""
from decimal import Decimal
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase

from apps.fleet.models import Personalizacion, Recurso, Servicio, ServicioPersonalizacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class CatalogoRLSTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='Sede RLS Catálogo', slug='sede-rls-cat')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A Cat', slug='empresa-rls-cat-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B Cat', slug='empresa-rls-cat-b')

    def test_aislamiento_servicios_entre_empresas(self):
        with scope.con_empresa(self.empresa_a):
            Servicio.objects.create(
                empresa=self.empresa_a,
                nombre='Tour Pesca A',
                slug='tour-pesca-a',
                precio_base=Decimal('5000.00'),
            )

        with scope.con_empresa(self.empresa_b):
            Servicio.objects.create(
                empresa=self.empresa_b,
                nombre='Tour Pesca B',
                slug='tour-pesca-b',
                precio_base=Decimal('6000.00'),
            )
            # Empresa B solo ve su propio servicio
            self.assertEqual(Servicio.objects.count(), 1)
            self.assertEqual(Servicio.objects.first().slug, 'tour-pesca-b')

    def test_aislamiento_recursos_entre_empresas(self):
        with scope.con_empresa(self.empresa_a):
            Recurso.objects.create(
                empresa=self.empresa_a,
                nombre='Panga Don Carlos A',
                capacidad_maxima=5,
            )

        with scope.con_empresa(self.empresa_b):
            Recurso.objects.create(
                empresa=self.empresa_b,
                nombre='Panga Don Ramon B',
                capacidad_maxima=4,
            )
            self.assertEqual(Recurso.objects.count(), 1)
            self.assertEqual(Recurso.objects.first().nombre, 'Panga Don Ramon B')

    def test_aislamiento_personalizaciones_y_m2m(self):
        with scope.con_empresa(self.empresa_a):
            serv_a = Servicio.objects.create(
                empresa=self.empresa_a,
                nombre='Tour A',
                slug='tour-a',
            )
            pers_a = Personalizacion.objects.create(
                empresa=self.empresa_a,
                nombre='Brunch Gourmet',
            )
            ServicioPersonalizacion.objects.create(
                servicio=serv_a,
                personalizacion=pers_a,
                precio=Decimal('250.00'),
            )

        with scope.con_empresa(self.empresa_b):
            serv_b = Servicio.objects.create(
                empresa=self.empresa_b,
                nombre='Tour B',
                slug='tour-b',
            )
            pers_b = Personalizacion.objects.create(
                empresa=self.empresa_b,
                nombre='Licencia B',
            )
            ServicioPersonalizacion.objects.create(
                servicio=serv_b,
                personalizacion=pers_b,
                precio=Decimal('150.00'),
            )

            self.assertEqual(Personalizacion.objects.count(), 1)
            self.assertEqual(Personalizacion.objects.first().nombre, 'Licencia B')
            self.assertEqual(ServicioPersonalizacion.objects.count(), 1)
            self.assertEqual(
                ServicioPersonalizacion.objects.first().personalizacion.nombre,
                'Licencia B',
            )
