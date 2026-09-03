from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import TestCase

from apps.tenancy.models import Empresa, Sede
from apps.testing import crear_flota

from .models import MOTIVO_SIN_PANGA, CupoDiario, Reserva, Vendedora, evaluar_cupo


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


class UnicidadPorEmpresaTests(TestCase):
    def test_dos_empresas_pueden_tener_cupo_diario_la_misma_fecha(self):
        empresa_a = crear_empresa(slug='empresa-a', nombre='A')
        empresa_b = crear_empresa(slug='empresa-b', nombre='B')
        CupoDiario.objects.create(empresa=empresa_a, fecha='2026-12-10', cupo_maximo=5)
        CupoDiario.objects.create(empresa=empresa_b, fecha='2026-12-10', cupo_maximo=8)  # no debe reventar

    def test_misma_empresa_no_puede_repetir_fecha_de_cupo(self):
        empresa = crear_empresa(slug='empresa-c', nombre='C')
        CupoDiario.objects.create(empresa=empresa, fecha='2026-12-11', cupo_maximo=5)
        with self.assertRaises(IntegrityError):
            CupoDiario.objects.create(empresa=empresa, fecha='2026-12-11', cupo_maximo=8)

    def test_dos_empresas_pueden_repetir_codigo_de_vendedora(self):
        User = get_user_model()
        empresa_a = crear_empresa(slug='empresa-a2', nombre='A2')
        empresa_b = crear_empresa(slug='empresa-b2', nombre='B2')
        Vendedora.objects.create(usuario=User.objects.create_user('v_a'), empresa=empresa_a, codigo='verano10')
        Vendedora.objects.create(usuario=User.objects.create_user('v_b'), empresa=empresa_b, codigo='verano10')


def datos_reserva(empresa, **overrides):
    crear_flota(empresa)
    base = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=15),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    base.update(overrides)
    return base


class CupoEmpresaAisladoTests(TestCase):
    def test_cupo_de_una_empresa_no_bloquea_a_otra(self):
        empresa_a = crear_empresa(slug='empresa-a3', nombre='A3')
        empresa_b = crear_empresa(slug='empresa-b3', nombre='B3')
        crear_flota(empresa_a, composicion=[(1, 3)])
        crear_flota(empresa_b, composicion=[(1, 3)])
        fecha = date.today() + timedelta(days=20)

        Reserva.objects.create(**datos_reserva(
            empresa_a, fecha=fecha, numero_personas=3, estado=Reserva.Estado.PAGADA,
        ))

        # La empresa A ya usó su única panga de 3; la B, con su propia panga de
        # 3 sin usar, debe seguir aceptando un grupo de 3.
        self.assertIsNone(evaluar_cupo(fecha, 3, empresa_b))
        self.assertEqual(evaluar_cupo(fecha, 3, empresa_a), MOTIVO_SIN_PANGA)
