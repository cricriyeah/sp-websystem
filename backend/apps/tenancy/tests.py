from datetime import date
from io import StringIO

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db.utils import IntegrityError
from django.test import RequestFactory, TestCase, TransactionTestCase

from apps.bookings.models import CupoDiario

from . import scope
from .admin_mixins import EmpresaScopedAdminMixin, EmpresaScopedUserAdminMixin
from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class ModelosTests(TestCase):
    # Slugs deliberadamente distintos de los que siembra
    # tenancy.0002_crear_sede_empresa_la_paz ('la-paz'/'sal-y-sol'): esa fila ya
    # existe, committeada, en cualquier base de test recien migrada -- un TestCase
    # normal la ve (su transaccion aisla lo que el test escribe, no lo que ya
    # estaba antes de que empezara). Reusar esos mismos slugs aqui reventaria con
    # IntegrityError en el primer test que corriera.
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede de prueba', slug='sede-test')

    def test_empresa_requiere_slug_unico(self):
        Empresa.objects.create(sede=self.sede, nombre='Empresa de prueba', slug='empresa-test')
        with self.assertRaises(IntegrityError):
            Empresa.objects.create(sede=self.sede, nombre='Otra', slug='empresa-test')

    def test_empresa_valida_prefijo_de_llaves_stripe(self):
        empresa = Empresa(
            sede=self.sede, nombre='Empresa de prueba', slug='empresa-test',
            stripe_secret_key='clave-mala',
        )
        with self.assertRaises(ValidationError):
            empresa.full_clean()

    def test_empresa_acepta_llaves_con_prefijo_correcto(self):
        empresa = Empresa(
            sede=self.sede, nombre='Empresa de prueba', slug='empresa-test',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_test_x',
        )
        empresa.full_clean()

    def test_membresia_es_unica_por_usuario_y_empresa(self):
        empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa de prueba', slug='empresa-test')
        user = User.objects.create_user(username='vendedora1', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.VENDEDORA)
        with self.assertRaises(IntegrityError):
            MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def test_related_name_membresias(self):
        empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa de prueba', slug='empresa-test')
        user = User.objects.create_user(username='jefe1', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE)
        self.assertEqual(user.membresias.count(), 1)


class BackfillSedeYEmpresaLaPazTests(TestCase):
    """`tenancy.0002_crear_sede_empresa_la_paz` corre en cualquier base de test
    recien migrada, asi que estas filas ya existen antes de que este test arranque
    -- lo unico que se verifica aqui es la forma del backfill, no que la migracion
    haya corrido (eso lo garantiza el propio test runner de Django)."""

    def test_sede_la_paz_existe_con_los_valores_esperados(self):
        sede = Sede.objects.get(slug='la-paz')
        self.assertEqual(sede.nombre, 'La Paz')
        self.assertEqual(sede.zona_horaria, 'America/Mazatlan')
        self.assertTrue(sede.activo)

    def test_empresa_sal_y_sol_existe_con_los_valores_esperados(self):
        empresa = Empresa.objects.get(slug='sal-y-sol')
        self.assertEqual(empresa.nombre, 'Sal y Sol Sportfishing')
        self.assertEqual(empresa.sede.slug, 'la-paz')
        self.assertTrue(empresa.activo)
        self.assertTrue(empresa.exclusiva)


class _CupoDiarioAdmin(EmpresaScopedAdminMixin, django_admin.ModelAdmin):
    """Admin de prueba para el mixin. `EmpresaScopedAdminMixin` es generico: se
    ejerce contra cualquier modelo con FK `empresa`. Se usa `CupoDiario` (real,
    con migracion) en vez de un modelo de test suelto -- uno sin migracion deja
    una tabla que solo existe durante esta clase y hace reventar el colector de
    borrado de `Empresa` (`no such table`) en cualquier otro test del proceso."""

    fields = ['fecha', 'cupo_maximo', 'empresa']


class EmpresaScopedAdminMixinTests(TestCase):
    def setUp(self):
        # slug 'sede-test' a proposito: 'la-paz' ya existe committeada por la
        # migracion 0002 y un TestCase la ve (ver ModelosTests arriba).
        sede = Sede.objects.create(nombre='La Paz', slug='sede-test')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')
        self.jefe = User.objects.create_user(username='jefe', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        self.admin = _CupoDiarioAdmin(CupoDiario, django_admin.site)

    def _request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    def test_get_fields_oculta_empresa_para_no_operador(self):
        with scope.con_empresa(self.empresa_a):
            fields = self.admin.get_fields(self._request(self.jefe))
        self.assertNotIn('empresa', fields)

    def test_get_fields_muestra_empresa_para_operador_en_creacion(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op', password='x', is_staff=True)
        operador.groups.add(grupo)
        with scope.como_operador_plataforma():
            fields = self.admin.get_fields(self._request(operador), obj=None)
        self.assertIn('empresa', fields)

    def test_get_fields_oculta_empresa_para_operador_en_edicion(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op2', password='x', is_staff=True)
        operador.groups.add(grupo)
        instancia = CupoDiario(fecha=date(2026, 12, 1), cupo_maximo=5, empresa=self.empresa_a)
        with scope.como_operador_plataforma():
            fields = self.admin.get_fields(self._request(operador), obj=instancia)
        self.assertNotIn('empresa', fields)

    def test_save_model_autoasigna_empresa_en_creacion_para_no_operador(self):
        obj = CupoDiario(fecha=date(2026, 12, 1), cupo_maximo=5)
        with scope.con_empresa(self.empresa_a):
            self.admin.save_model(self._request(self.jefe), obj, form=None, change=False)
        self.assertEqual(obj.empresa_id, self.empresa_a.id)

    def test_get_queryset_filtra_por_empresa_para_no_operador(self):
        CupoDiario.objects.create(fecha=date(2026, 12, 1), cupo_maximo=5, empresa=self.empresa_a)
        CupoDiario.objects.create(fecha=date(2026, 12, 2), cupo_maximo=5, empresa=self.empresa_b)
        with scope.con_empresa(self.empresa_a):
            fechas = set(self.admin.get_queryset(self._request(self.jefe)).values_list('fecha', flat=True))
        self.assertEqual(fechas, {date(2026, 12, 1)})

    def test_get_queryset_no_filtra_para_operador(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op3', password='x', is_staff=True)
        operador.groups.add(grupo)
        CupoDiario.objects.create(fecha=date(2026, 12, 1), cupo_maximo=5, empresa=self.empresa_a)
        CupoDiario.objects.create(fecha=date(2026, 12, 2), cupo_maximo=5, empresa=self.empresa_b)
        with scope.como_operador_plataforma():
            count = self.admin.get_queryset(self._request(operador)).count()
        self.assertEqual(count, 2)


class _UserAdminDePrueba(EmpresaScopedUserAdminMixin, BaseUserAdmin, django_admin.ModelAdmin):
    pass


class EmpresaScopedUserAdminMixinTests(TestCase):
    def setUp(self):
        # slug 'sede-test': 'la-paz' ya existe committeada por la migracion 0002.
        sede = Sede.objects.create(nombre='La Paz', slug='sede-test')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')

        self.jefe_a = User.objects.create_user(username='jefe-a', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)

        self.vendedora_b = User.objects.create_user(username='vend-b', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(
            user=self.vendedora_b, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        self.admin = _UserAdminDePrueba(User, django_admin.site)

    def _request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    def test_get_queryset_no_cruza_empresas(self):
        with scope.con_empresa(self.empresa_a):
            qs = self.admin.get_queryset(self._request(self.jefe_a))
        self.assertIn(self.jefe_a, qs)
        self.assertNotIn(self.vendedora_b, qs)

    def test_get_queryset_operador_ve_todo(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op', password='x', is_staff=True)
        operador.groups.add(grupo)
        with scope.como_operador_plataforma():
            qs = self.admin.get_queryset(self._request(operador))
        self.assertIn(self.jefe_a, qs)
        self.assertIn(self.vendedora_b, qs)

    def test_no_ve_ni_puede_acceder_a_ficha_de_usuario_ajeno(self):
        with scope.con_empresa(self.empresa_a):
            self.assertFalse(
                self.admin.has_view_permission(self._request(self.jefe_a), self.vendedora_b)
            )
            self.assertFalse(
                self.admin.has_change_permission(self._request(self.jefe_a), self.vendedora_b)
            )

    def test_has_add_permission_falso_para_no_operador(self):
        with scope.con_empresa(self.empresa_a):
            self.assertFalse(self.admin.has_add_permission(self._request(self.jefe_a)))

    def test_get_fieldsets_de_jefe_no_incluye_campos_de_permisos_completos(self):
        with scope.con_empresa(self.empresa_a):
            fieldsets = self.admin.get_fieldsets(self._request(self.jefe_a), self.jefe_a)
        campos_planos = {campo for _, opciones in fieldsets for campo in opciones.get('fields', ())}
        self.assertNotIn('is_superuser', campos_planos)
        self.assertNotIn('user_permissions', campos_planos)
        self.assertNotIn('groups', campos_planos)
        self.assertIn('is_active', campos_planos)

    def test_get_fieldsets_de_operador_incluye_todo(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op2', password='x', is_staff=True)
        operador.groups.add(grupo)
        with scope.como_operador_plataforma():
            fieldsets = self.admin.get_fieldsets(self._request(operador), operador)
        campos_planos = {campo for _, opciones in fieldsets for campo in opciones.get('fields', ())}
        self.assertIn('is_superuser', campos_planos)

    def test_post_completo_inyectando_is_superuser_no_escala(self):
        """Prueba directa de H1: simula un jefe enviando el form completo del
        changelist con is_superuser=on inyectado a mano (bypaseando el HTML
        real, que ya no pinta el campo) -- ModelForm solo procesa los campos
        de `fields` (derivados de get_fieldsets), asi que un campo ausente de
        ahi nunca llega a `cleaned_data` sin importar que traiga el POST."""
        with scope.con_empresa(self.empresa_a):
            request = self._request(self.jefe_a)
            fieldsets = self.admin.get_fieldsets(request, self.jefe_a)
            form_class = self.admin.get_form(
                request, self.jefe_a, change=True, fields=flatten_fieldsets(fieldsets),
            )
            form = form_class(
                data={'is_superuser': 'on', 'is_active': 'on', 'username': 'jefe-a'},
                instance=self.jefe_a,
            )
            self.assertTrue(form.is_valid(), form.errors)
            usuario_actualizado = form.save(commit=False)
            self.assertFalse(usuario_actualizado.is_superuser)


class MigrarLaPazAEmpresaTests(TestCase):
    """`tenancy.0002_crear_sede_empresa_la_paz` ya siembra la Sede 'la-paz' y la
    Empresa 'sal-y-sol' -- esta clase no las vuelve a crear (colisionaria con
    IntegrityError, mismo motivo que ModelosTests usa slugs distintos)."""

    def setUp(self):
        call_command('setup_roles', stdout=StringIO())
        self.empresa = Empresa.objects.get(slug='sal-y-sol')

        self.operador = User.objects.create_superuser(username='admin_sistema', password='x')
        self.jefe1 = User.objects.create_superuser(username='jefe1', password='x')
        self.vendedora1 = User.objects.create_user(username='vend1', password='x', is_staff=True)
        self.vendedora1.groups.add(Group.objects.get(name='Vendedora'))

    def test_sin_operador_falla_explicito(self):
        with self.assertRaises(CommandError):
            call_command('migrar_la_paz_a_empresa', stdout=StringIO())

    def test_migra_operador_jefes_y_vendedoras(self):
        call_command('migrar_la_paz_a_empresa', operador='admin_sistema', stdout=StringIO())

        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_superuser)
        self.assertTrue(self.operador.groups.filter(name='OperadorPlataforma').exists())
        self.assertFalse(MembresiaEmpresa.objects.filter(user=self.operador).exists())

        self.jefe1.refresh_from_db()
        self.assertFalse(self.jefe1.is_superuser)
        self.assertTrue(self.jefe1.groups.filter(name='Jefe').exists())
        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=self.jefe1, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE,
        ).exists())

        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=self.vendedora1, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        ).exists())

    def test_dry_run_no_cambia_nada(self):
        call_command('migrar_la_paz_a_empresa', operador='admin_sistema', dry_run=True, stdout=StringIO())
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_superuser)
        self.assertFalse(MembresiaEmpresa.objects.exists())

    def test_sin_setup_roles_previo_falla_explicito(self):
        Group.objects.all().delete()
        with self.assertRaises(CommandError):
            call_command('migrar_la_paz_a_empresa', operador='admin_sistema', stdout=StringIO())

    def test_sin_empresa_sal_y_sol_falla_explicito(self):
        from apps.fleet.models import Recurso, Servicio
        Recurso.objects.filter(empresa=self.empresa).delete()
        Servicio.objects.filter(empresa=self.empresa).delete()
        self.empresa.delete()
        with self.assertRaises(CommandError):
            call_command('migrar_la_paz_a_empresa', operador='admin_sistema', stdout=StringIO())
