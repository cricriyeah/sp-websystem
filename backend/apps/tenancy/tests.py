from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase

from django.contrib.auth import get_user_model

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
