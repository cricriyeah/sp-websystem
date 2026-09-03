from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase

from apps.tenancy.models import Empresa, Sede

from .models import CupoDiario, Vendedora


class SetupRolesTests(TestCase):
    def test_jefe_no_tiene_permisos_sobre_auth_group(self):
        call_command('setup_roles')
        jefe = Group.objects.get(name='Jefe')
        self.assertFalse(
            jefe.permissions.filter(content_type__app_label='auth', content_type__model='group').exists()
        )
        self.assertTrue(jefe.permissions.filter(codename='view_user').exists())
        self.assertTrue(jefe.permissions.filter(codename='change_user').exists())
        self.assertFalse(jefe.permissions.filter(codename='add_user').exists())
        self.assertFalse(jefe.permissions.filter(codename='delete_user').exists())

    def test_operador_plataforma_si_tiene_auth_group(self):
        call_command('setup_roles')
        operador = Group.objects.get(name='OperadorPlataforma')
        self.assertTrue(
            operador.permissions.filter(content_type__app_label='auth', content_type__model='group').exists()
        )
        self.assertTrue(operador.permissions.filter(codename='add_user').exists())


def crear_empresa(**overrides):
    """Sede/Empresa de prueba para tests de esta app que no usan `EmpresaTestCase`.

    Slugs deliberadamente distintos de los que siembra `tenancy.0002_crear_sede_empresa_la_paz`
    ('la-paz'/'sal-y-sol') -- esas filas ya existen, committeadas, en cualquier base de test
    recien migrada; reusar el mismo slug de Empresa aqui chocaria con IntegrityError en el
    primer test que corriera (Sede usa get_or_create asi que no rompe, pero Empresa usa
    `.create()` directo).
    """
    sede, _ = Sede.objects.get_or_create(
        slug=overrides.pop('sede_slug', 'sede-de-prueba-b1'),
        defaults={'nombre': 'Sede de prueba B1', 'zona_horaria': 'America/Mazatlan', 'activo': True},
    )
    base = {
        'sede': sede, 'nombre': 'Empresa de prueba B1', 'slug': 'empresa-de-prueba-b1',
        'activo': True, 'exclusiva': True,
    }
    base.update(overrides)
    return Empresa.objects.create(**base)


class ReservaEmpresaFKTests(TestCase):
    def test_empresa_protegida_contra_borrado_con_cupo_diario(self):
        empresa = crear_empresa()
        CupoDiario.objects.create(empresa=empresa, fecha='2026-12-01', cupo_maximo=5)

        with self.assertRaises(ProtectedError):
            empresa.delete()

    def test_empresa_protegida_contra_borrado_con_vendedora(self):
        empresa = crear_empresa(slug='otra-empresa-b1', nombre='Otra')
        usuario = get_user_model().objects.create_user('vendedora1', password='x')
        Vendedora.objects.create(usuario=usuario, empresa=empresa, codigo='ref1')

        with self.assertRaises(ProtectedError):
            empresa.delete()


class EmpresaObligatoriaTests(TestCase):
    def test_cupo_diario_sin_empresa_revienta(self):
        with self.assertRaises(IntegrityError):
            CupoDiario.objects.create(fecha='2026-12-05', cupo_maximo=5)
