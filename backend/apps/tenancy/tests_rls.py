"""Verificacion de las politicas RLS de 0003_rls.py contra Postgres.

Solo tienen sentido en Postgres -- sqlite no tiene RLS. `skipUnless` salta
toda la clase en local; el CI de Postgres es quien de verdad la ejerce.
"""
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase

from . import scope
from .models import Empresa, Sede


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class RLSTests(TransactionTestCase):
    def setUp(self):
        # Slugs deliberadamente distintos de los que siembra
        # tenancy.0002_crear_sede_empresa_la_paz ('la-paz'/'sal-y-sol'): esa fila
        # ya existe, committeada, en cualquier base recien migrada.
        sede = Sede.objects.create(nombre='Sede RLS', slug='sede-rls')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-rls-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-rls-b')

    def test_rol_de_test_no_es_superusuario_ni_bypassrls(self):
        # Primera aserción de la clase -- si esto falla, TODA la suite de RLS
        # pasaria en verde sin haber probado nada.
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user'
            )
            rolsuper, rolbypassrls = cursor.fetchone()
        if rolsuper or rolbypassrls:
            self.fail(
                f'El rol de test ({connection.settings_dict["USER"]}) tiene '
                f'rolsuper={rolsuper} rolbypassrls={rolbypassrls} -- RLS no '
                f'protege nada con este rol. Ver runbook de CI (seccion Infra).'
            )

    def test_dos_empresas_no_se_ven_por_orm(self):
        from apps.fleet.models import Embarcacion

        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Panga A', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
        with scope.con_empresa(self.empresa_b):
            Embarcacion.objects.create(
                nombre='Panga B', clase='chica', capacidad_maxima=3, empresa=self.empresa_b,
            )
            self.assertEqual(Embarcacion.objects.count(), 1)
            self.assertEqual(Embarcacion.objects.first().nombre, 'Panga B')

    def test_sin_set_local_devuelve_cero_filas_no_excepcion(self):
        from apps.fleet.models import Embarcacion

        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Panga A', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
        # Sin ningun con_empresa activo: SET LOCAL nunca se emitio en esta
        # transaccion nueva -- NULLIF(current_setting(...), '')::int es NULL,
        # la politica USING es NULL (falsa), cero filas.
        self.assertEqual(Embarcacion.objects.count(), 0)

    def test_insert_sin_alcance_falla(self):
        from django.db.utils import ProgrammingError

        from apps.fleet.models import Embarcacion

        with self.assertRaises(ProgrammingError):
            Embarcacion.objects.create(
                nombre='Sin alcance', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
