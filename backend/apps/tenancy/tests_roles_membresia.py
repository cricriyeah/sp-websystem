# backend/apps/tenancy/tests_roles_membresia.py
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedUserAdminMixin
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.tenancy.permisos_unfold import puede_ver_finanzas

User = get_user_model()


class RolesMembresiaTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())

        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede Roles Test', slug='sede-roles-test')
            self.empresa_a = Empresa.objects.create(
                sede=self.sede, nombre='Empresa Roles A', slug='empresa-roles-a',
            )
            self.empresa_b = Empresa.objects.create(
                sede=self.sede, nombre='Empresa Roles B', slug='empresa-roles-b',
            )

            # Jefe con membresía JEFE y grupo Django Jefe
            self.jefe_a = User.objects.create_user(
                username='jefe_test_a', password='PasswordValida123!', is_staff=True,
            )
            self.jefe_a.groups.add(Group.objects.get(name='Jefe'))
            MembresiaEmpresa.objects.create(
                user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
            )

            # Vendedora con membresía VENDEDORA y grupo Django Vendedora
            self.vendedora_a = User.objects.create_user(
                username='vendedora_test_a', password='PasswordValida123!', is_staff=True,
            )
            self.vendedora_a.groups.add(Group.objects.get(name='Vendedora'))
            MembresiaEmpresa.objects.create(
                user=self.vendedora_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.VENDEDORA,
            )

            # Usuario sin membresía ni grupos
            self.usuario_sin_membresia = User.objects.create_user(
                username='sin_membresia_test', password='PasswordValida123!', is_staff=True,
            )

            # Usuario en el grupo Jefe pero SIN membresía JEFE
            self.usuario_grupo_jefe_sin_membresia = User.objects.create_user(
                username='solo_grupo_jefe', password='PasswordValida123!', is_staff=True,
            )
            self.usuario_grupo_jefe_sin_membresia.groups.add(Group.objects.get(name='Jefe'))

            # Usuario con membresía JEFE pero SIN grupo Jefe
            self.usuario_membresia_jefe_sin_grupo = User.objects.create_user(
                username='solo_membresia_jefe', password='PasswordValida123!', is_staff=True,
            )
            MembresiaEmpresa.objects.create(
                user=self.usuario_membresia_jefe_sin_grupo,
                empresa=self.empresa_a,
                rol=MembresiaEmpresa.Rol.JEFE,
            )

            # Operador de plataforma (sin membresía)
            self.operador = User.objects.create_user(
                username='operador_test', password='PasswordValida123!', is_staff=True,
            )
            self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

        self.factory = RequestFactory()
        from django.contrib.admin import ModelAdmin, site
        from django.contrib.auth.models import User as UserModel

        # El mixin va delante de un ModelAdmin real, como en UserAdmin.
        class _AdminDePrueba(EmpresaScopedUserAdminMixin, ModelAdmin):
            pass

        self.admin_mixin = _AdminDePrueba(UserModel, site)

    def test_rol_en(self):
        """Verifica la resolución de roles por MembresiaEmpresa."""
        self.assertEqual(scope.rol_en(self.jefe_a, self.empresa_a), MembresiaEmpresa.Rol.JEFE)
        self.assertEqual(scope.rol_en(self.vendedora_a, self.empresa_a), MembresiaEmpresa.Rol.VENDEDORA)
        self.assertIsNone(scope.rol_en(self.usuario_sin_membresia, self.empresa_a))
        self.assertIsNone(scope.rol_en(self.jefe_a, self.empresa_b))
        self.assertIsNone(scope.rol_en(AnonymousUser(), self.empresa_a))
        self.assertIsNone(scope.rol_en(None, self.empresa_a))
        self.assertIsNone(scope.rol_en(self.jefe_a, None))
        self.assertIsNone(scope.rol_en(self.operador, self.empresa_a))

        # Si el operador tuviese membresía explícita en una empresa, rol_en la reporta
        with scope.como_operador_plataforma():
            MembresiaEmpresa.objects.create(
                user=self.operador, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.JEFE,
            )
        self.assertEqual(scope.rol_en(self.operador, self.empresa_b), MembresiaEmpresa.Rol.JEFE)

    def test_es_jefe(self):
        """Verifica que es_jefe sea True solo con membresía JEFE en esa empresa."""
        self.assertTrue(scope.es_jefe(self.jefe_a, self.empresa_a))
        self.assertFalse(scope.es_jefe(self.vendedora_a, self.empresa_a))
        self.assertFalse(scope.es_jefe(self.usuario_sin_membresia, self.empresa_a))
        self.assertFalse(scope.es_jefe(self.jefe_a, self.empresa_b))
        self.assertFalse(scope.es_jefe(AnonymousUser(), self.empresa_a))
        self.assertFalse(scope.es_jefe(None, self.empresa_a))
        self.assertFalse(scope.es_jefe(self.jefe_a, None))
        self.assertFalse(scope.es_jefe(self.operador, self.empresa_a))

    def test_usuario_grupo_jefe_sin_membresia_no_es_jefe(self):
        """Un usuario en el grupo Django 'Jefe' SIN membresía JEFE no es jefe."""
        self.assertTrue(self.usuario_grupo_jefe_sin_membresia.groups.filter(name='Jefe').exists())
        self.assertFalse(scope.es_jefe(self.usuario_grupo_jefe_sin_membresia, self.empresa_a))

        request = self.factory.get('/admin/')
        request.user = self.usuario_grupo_jefe_sin_membresia
        with scope.con_empresa(self.empresa_a):
            self.assertFalse(scope.es_jefe_actual(request))
            self.assertFalse(puede_ver_finanzas(request))

    def test_membresia_jefe_sin_grupo_jefe_si_es_jefe(self):
        """Una membresía JEFE sin el grupo Django Jefe sí es jefe para las reglas de negocio."""
        self.assertFalse(self.usuario_membresia_jefe_sin_grupo.groups.filter(name='Jefe').exists())
        self.assertTrue(scope.es_jefe(self.usuario_membresia_jefe_sin_grupo, self.empresa_a))

        request = self.factory.get('/admin/')
        request.user = self.usuario_membresia_jefe_sin_grupo
        with scope.con_empresa(self.empresa_a):
            self.assertTrue(scope.es_jefe_actual(request))
            self.assertTrue(puede_ver_finanzas(request))

    def test_helpers_con_request_actual(self):
        """Verifica es_jefe_actual, tiene_rol_actual y es_vendedora_actual con request."""
        request = self.factory.get('/admin/')

        with scope.con_empresa(self.empresa_a):
            # Jefe
            request.user = self.jefe_a
            self.assertTrue(scope.es_jefe_actual(request))
            self.assertTrue(scope.tiene_rol_actual(request))
            self.assertFalse(scope.es_vendedora_actual(request))

            # Vendedora
            request.user = self.vendedora_a
            self.assertFalse(scope.es_jefe_actual(request))
            self.assertTrue(scope.tiene_rol_actual(request))
            self.assertTrue(scope.es_vendedora_actual(request))

            # Usuario sin membresía
            request.user = self.usuario_sin_membresia
            self.assertFalse(scope.es_jefe_actual(request))
            self.assertFalse(scope.tiene_rol_actual(request))
            self.assertFalse(scope.es_vendedora_actual(request))

            # Usuario anónimo
            request.user = AnonymousUser()
            self.assertFalse(scope.es_jefe_actual(request))
            self.assertFalse(scope.tiene_rol_actual(request))
            self.assertFalse(scope.es_vendedora_actual(request))

        # Fuera de con_empresa (sin empresa actual)
        request.user = self.jefe_a
        self.assertFalse(scope.es_jefe_actual(request))
        self.assertFalse(scope.tiene_rol_actual(request))
        self.assertFalse(scope.es_vendedora_actual(request))

    def test_admin_mixin_es_jefe(self):
        """Verifica que EmpresaScopedUserAdminMixin._es_jefe delegue a scope.es_jefe."""
        self.assertTrue(self.admin_mixin._es_jefe(self.jefe_a, self.empresa_a))
        self.assertFalse(self.admin_mixin._es_jefe(self.vendedora_a, self.empresa_a))
        self.assertFalse(self.admin_mixin._es_jefe(self.operador, self.empresa_a))
        self.assertFalse(self.admin_mixin._es_jefe(AnonymousUser(), self.empresa_a))
        self.assertFalse(self.admin_mixin._es_jefe(self.jefe_a, None))
        self.assertFalse(self.admin_mixin._es_jefe(self.usuario_grupo_jefe_sin_membresia, self.empresa_a))
        self.assertTrue(self.admin_mixin._es_jefe(self.usuario_membresia_jefe_sin_grupo, self.empresa_a))

    def test_admin_mixin_has_change_permission_regla_no_editar_jefe(self):
        """Un jefe no puede editar a otro jefe (determinado por MembresiaEmpresa.Rol.JEFE)."""
        request = self.factory.get('/admin/auth/user/')
        request.user = self.jefe_a

        with scope.con_empresa(self.empresa_a):
            # No puede editar al usuario con membresía JEFE (aunque no tenga grupo Jefe)
            self.assertFalse(
                self.admin_mixin.has_change_permission(request, self.usuario_membresia_jefe_sin_grupo)
            )
            # No puede editar al operador
            self.assertFalse(
                self.admin_mixin.has_change_permission(request, self.operador)
            )
            # Sí puede editar a sí mismo
            self.assertTrue(
                self.admin_mixin.has_change_permission(request, self.jefe_a)
            )
