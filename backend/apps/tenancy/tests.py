from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.utils import IntegrityError
from django.test import RequestFactory, TestCase, TransactionTestCase

from . import scope
from .admin_mixins import EmpresaScopedAdminMixin
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


class ModeloDePrueba(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=50)

    class Meta:
        app_label = 'tenancy'


class ModeloDePruebaAdmin(EmpresaScopedAdminMixin, django_admin.ModelAdmin):
    fields = ['nombre', 'empresa']


class EmpresaScopedAdminMixinTests(TestCase):
    # ModeloDePrueba no tiene migracion (es de test), asi que el test runner no
    # le crea tabla al construir la base -- se crea/borra a mano por clase.
    # DDL fuera del atomic de TestCase: sqlite no deja al schema_editor apagar
    # los FK checks a media transaccion, asi que va antes de super().setUpClass().
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(ModeloDePrueba)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(ModeloDePrueba)

    def setUp(self):
        # slug 'sede-test' a proposito: 'la-paz' ya existe committeada por la
        # migracion 0002 y un TestCase la ve (ver ModelosTests arriba).
        sede = Sede.objects.create(nombre='La Paz', slug='sede-test')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')
        self.jefe = User.objects.create_user(username='jefe', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        self.admin = ModeloDePruebaAdmin(ModeloDePrueba, django_admin.site)

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
        instancia = ModeloDePrueba(nombre='x', empresa=self.empresa_a)
        with scope.como_operador_plataforma():
            fields = self.admin.get_fields(self._request(operador), obj=instancia)
        self.assertNotIn('empresa', fields)

    def test_save_model_autoasigna_empresa_en_creacion_para_no_operador(self):
        obj = ModeloDePrueba(nombre='x')
        with scope.con_empresa(self.empresa_a):
            self.admin.save_model(self._request(self.jefe), obj, form=None, change=False)
        self.assertEqual(obj.empresa_id, self.empresa_a.id)

    def test_get_queryset_filtra_por_empresa_para_no_operador(self):
        ModeloDePrueba.objects.create(nombre='de a', empresa=self.empresa_a)
        ModeloDePrueba.objects.create(nombre='de b', empresa=self.empresa_b)
        with scope.con_empresa(self.empresa_a):
            nombres = set(self.admin.get_queryset(self._request(self.jefe)).values_list('nombre', flat=True))
        self.assertEqual(nombres, {'de a'})

    def test_get_queryset_no_filtra_para_operador(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op3', password='x', is_staff=True)
        operador.groups.add(grupo)
        ModeloDePrueba.objects.create(nombre='de a', empresa=self.empresa_a)
        ModeloDePrueba.objects.create(nombre='de b', empresa=self.empresa_b)
        with scope.como_operador_plataforma():
            count = self.admin.get_queryset(self._request(operador)).count()
        self.assertEqual(count, 2)
