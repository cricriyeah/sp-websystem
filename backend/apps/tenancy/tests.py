from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase

from django.contrib.auth import get_user_model

from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class ModelosTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='La Paz', slug='la-paz')

    def test_empresa_requiere_slug_unico(self):
        Empresa.objects.create(sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol')
        with self.assertRaises(IntegrityError):
            Empresa.objects.create(sede=self.sede, nombre='Otra', slug='sal-y-sol')

    def test_empresa_valida_prefijo_de_llaves_stripe(self):
        empresa = Empresa(
            sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='clave-mala',
        )
        with self.assertRaises(ValidationError):
            empresa.full_clean()

    def test_empresa_acepta_llaves_con_prefijo_correcto(self):
        empresa = Empresa(
            sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_test_x',
        )
        empresa.full_clean()

    def test_membresia_es_unica_por_usuario_y_empresa(self):
        empresa = Empresa.objects.create(sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol')
        user = User.objects.create_user(username='vendedora1', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.VENDEDORA)
        with self.assertRaises(IntegrityError):
            MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def test_related_name_membresias(self):
        empresa = Empresa.objects.create(sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol')
        user = User.objects.create_user(username='jefe1', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE)
        self.assertEqual(user.membresias.count(), 1)
