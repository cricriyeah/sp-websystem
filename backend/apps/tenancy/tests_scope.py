# backend/apps/tenancy/tests_scope.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.test import TransactionTestCase

from . import scope
from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class ScopePrimitivoTests(TransactionTestCase):
    def setUp(self):
        # slug 'sede-test' a proposito: 'la-paz' ya existe committeada por la
        # migracion de datos 0002 y chocaria con IntegrityError (ver reporte T2).
        sede = Sede.objects.create(nombre='La Paz', slug='sede-test')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')

    def test_con_empresa_no_falla_con_el_mismo_valor_anidado(self):
        with scope.con_empresa(self.empresa_a):
            with scope.con_empresa(self.empresa_a):
                pass  # no-op idempotente, no debe lanzar

    def test_con_empresa_falla_con_valor_distinto_anidado(self):
        with scope.con_empresa(self.empresa_a):
            with self.assertRaises(RuntimeError):
                with scope.con_empresa(self.empresa_b):
                    pass

    def test_con_empresa_restaura_al_salir(self):
        with scope.con_empresa(self.empresa_a):
            pass
        self.assertIsNone(getattr(connection, 'alcance_actual', None))

    def test_con_empresa_restaura_el_valor_exterior_tras_anidar(self):
        with scope.con_empresa(self.empresa_a):
            with scope.con_empresa(self.empresa_a):
                pass
            self.assertEqual(connection.alcance_actual, ('empresa', self.empresa_a.id))

    def test_resolver_membresia_sin_membresias_lanza_permission_denied(self):
        user = User.objects.create_user(username='huerfano', password='x')
        with self.assertRaises(PermissionDenied):
            scope.resolver_membresia_o_403(user)

    def test_resolver_membresia_con_dos_membresias_lanza_permission_denied(self):
        user = User.objects.create_user(username='dos', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.JEFE)
        with self.assertRaises(PermissionDenied):
            scope.resolver_membresia_o_403(user)

    def test_resolver_membresia_con_una_membresia_devuelve_con_empresa(self):
        user = User.objects.create_user(username='uno', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        with scope.resolver_membresia_o_403(user):
            self.assertEqual(connection.alcance_actual, ('empresa', self.empresa_a.id))

    def test_resolver_membresia_operador_de_plataforma(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        user = User.objects.create_user(username='operador', password='x')
        user.groups.add(grupo)
        with scope.resolver_membresia_o_403(user):
            self.assertEqual(connection.alcance_actual, ('operador',))

    def test_resolver_empresa_publica_404_si_no_existe(self):
        with self.assertRaises(Http404):
            scope.resolver_empresa_publica('no-existe')

    def test_resolver_empresa_publica_404_si_pausada(self):
        self.empresa_a.activo = False
        self.empresa_a.save()
        with self.assertRaises(Http404):
            scope.resolver_empresa_publica('empresa-a')

    def test_resolver_empresa_de_dinero_ignora_activo(self):
        self.empresa_a.activo = False
        self.empresa_a.save()
        empresa = scope.resolver_empresa_de_dinero('empresa-a')
        self.assertEqual(empresa.pk, self.empresa_a.pk)

    def test_es_operador_plataforma(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        user = User.objects.create_user(username='op', password='x')
        self.assertFalse(scope.es_operador_plataforma(user))
        user.groups.add(grupo)
        self.assertTrue(scope.es_operador_plataforma(user))
