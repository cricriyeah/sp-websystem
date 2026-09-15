import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenancy import scope

from apps.fleet.models import (
    Capitan,
    CodigoPromocional,
    Embarcacion,
    ExtrasItem,
    PuntoEncuentro,
)
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.testing import OperadorTestCase, crear_flota, crear_servicio_pesca

from .admin import AgendaAdmin, CheckoutAbandonadoAdmin
from .panorama import armar_panorama
from .models import (
    MOTIVO_SIN_PANGA,
    Agenda,
    CheckoutAbandonado,
    CupoDiario,
    Reserva,
    ReservaExtra,
    Vendedora,
    evaluar_codigo_promocional,
    evaluar_cupo,
)


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


class ReservaEmpresaFKTests(OperadorTestCase):
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


class EmpresaObligatoriaTests(OperadorTestCase):
    def test_cupo_diario_sin_empresa_revienta(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CupoDiario.objects.create(fecha='2026-12-05', cupo_maximo=5)


class UnicidadPorEmpresaTests(OperadorTestCase):
    def test_dos_empresas_pueden_tener_cupo_diario_la_misma_fecha(self):
        empresa_a = crear_empresa(slug='empresa-a', nombre='A')
        empresa_b = crear_empresa(slug='empresa-b', nombre='B')
        CupoDiario.objects.create(empresa=empresa_a, fecha='2026-12-10', cupo_maximo=5)
        CupoDiario.objects.create(empresa=empresa_b, fecha='2026-12-10', cupo_maximo=8)  # no debe reventar

    def test_misma_empresa_no_puede_repetir_fecha_de_cupo(self):
        empresa = crear_empresa(slug='empresa-c', nombre='C')
        CupoDiario.objects.create(empresa=empresa, fecha='2026-12-11', cupo_maximo=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CupoDiario.objects.create(empresa=empresa, fecha='2026-12-11', cupo_maximo=8)

    def test_dos_empresas_pueden_repetir_codigo_de_vendedora(self):
        User = get_user_model()
        empresa_a = crear_empresa(slug='empresa-a2', nombre='A2')
        empresa_b = crear_empresa(slug='empresa-b2', nombre='B2')
        Vendedora.objects.create(usuario=User.objects.create_user('v_a'), empresa=empresa_a, codigo='verano10')
        Vendedora.objects.create(usuario=User.objects.create_user('v_b'), empresa=empresa_b, codigo='verano10')


def datos_reserva(empresa, **overrides):
    empresa_real = overrides.get('empresa', empresa)
    crear_flota(empresa_real)
    base = {
        'empresa': empresa_real,
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
    if 'servicio' not in overrides and 'paquete' not in overrides:
        base['servicio'] = crear_servicio_pesca(empresa_real)
    base.update(overrides)
    return base


def crear_reserva(empresa, **overrides):
    """`Reserva` de prueba creada dentro de `con_empresa(empresa)` — para las
    clases que NO corren bajo `OperadorTestCase` (las que pegan a una vista, un
    comando que itera Empresas, o un callback on_commit que reabre alcance)."""
    with scope.con_empresa(empresa):
        return Reserva.objects.create(**datos_reserva(empresa, **overrides))


class CupoEmpresaAisladoTests(OperadorTestCase):
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


class CodigoPromocionalEmpresaTests(OperadorTestCase):
    def test_codigo_de_una_empresa_no_valida_en_otra(self):
        empresa_a = crear_empresa(slug='empresa-a4', nombre='A4')
        empresa_b = crear_empresa(slug='empresa-b4', nombre='B4')
        CodigoPromocional.objects.create(
            empresa=empresa_a, codigo='VERANO10', porcentaje_descuento=10, activo=True,
        )

        self.assertIsNotNone(evaluar_codigo_promocional('VERANO10', 'x@example.com', empresa_a))
        self.assertIsNone(evaluar_codigo_promocional('VERANO10', 'x@example.com', empresa_b))


class ConsistenciaEmpresaReservaTests(OperadorTestCase):
    def test_vendedora_de_otra_empresa_no_se_puede_asignar(self):
        empresa_a = crear_empresa(slug='empresa-a5', nombre='A5')
        empresa_b = crear_empresa(slug='empresa-b5', nombre='B5')
        vendedora_b = Vendedora.objects.create(
            usuario=get_user_model().objects.create_user('vb5'), empresa=empresa_b, codigo='vb5',
        )
        reserva = Reserva(**datos_reserva(empresa_a, vendedora=vendedora_b))

        with self.assertRaises(ValidationError):
            reserva.full_clean()


class ConsistenciaEmpresaExtrasTests(OperadorTestCase):
    def test_extra_de_otra_empresa_no_se_puede_asociar(self):
        empresa_a = crear_empresa(slug='empresa-a6', nombre='A6')
        empresa_b = crear_empresa(slug='empresa-b6', nombre='B6')
        extra_b = ExtrasItem.objects.create(
            empresa=empresa_b, tipo=ExtrasItem.Tipo.BRUNCH, nombre='Brunch', precio=Decimal('100'), activo=True,
        )
        reserva = Reserva.objects.create(**datos_reserva(empresa_a))

        extra = ReservaExtra(reserva=reserva, extras_item=extra_b)
        with self.assertRaises(ValidationError):
            extra.full_clean()


class AdminScopingTests(OperadorTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.empresa_a = crear_empresa(slug='empresa-a8', nombre='A8')
        self.empresa_b = crear_empresa(slug='empresa-b8', nombre='B8')
        r_a = Reserva.objects.create(**datos_reserva(self.empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO))
        r_b = Reserva.objects.create(**datos_reserva(self.empresa_b, estado=Reserva.Estado.PENDIENTE_PAGO))
        Reserva.objects.filter(pk__in=[r_a.pk, r_b.pk]).update(
            creado_en=timezone.now() - timedelta(hours=3)
        )

    def test_checkout_abandonado_admin_aisla_por_empresa(self):
        admin = CheckoutAbandonadoAdmin(CheckoutAbandonado, admin_site=mock.Mock())
        request = self.factory.get('/admin/bookings/checkoutabandonado/')
        request.user = mock.Mock()
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa_a), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            filas = list(admin.get_queryset(request))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].empresa_id, self.empresa_a.id)

    def test_agenda_admin_aisla_por_empresa(self):
        reserva_a = Reserva.objects.create(**datos_reserva(
            self.empresa_a, estado=Reserva.Estado.PAGADA, fecha=date.today() + timedelta(days=3),
        ))
        Reserva.objects.create(**datos_reserva(
            self.empresa_b, estado=Reserva.Estado.PAGADA, fecha=date.today() + timedelta(days=3),
        ))
        admin = AgendaAdmin(Agenda, admin_site=mock.Mock())
        request = self.factory.get('/admin/bookings/agenda/')
        request.user = mock.Mock()
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa_a), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            filas = list(admin.get_queryset(request))
        self.assertEqual([f.pk for f in filas], [reserva_a.pk])


class AltaVendedoraTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa(slug='empresa-alta', nombre='Alta')
        self.jefe = get_user_model().objects.create_user('jefe1', password='x', is_staff=True)
        self.jefe.groups.add(Group.objects.create(name='Jefe'))
        Group.objects.get_or_create(name='Vendedora')
        MembresiaEmpresa.objects.create(user=self.jefe, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def test_jefe_da_de_alta_vendedora_sin_elegir_empresa(self):
        self.client.force_login(self.jefe)
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            response = self.client.post(reverse('admin:bookings_user_dar_de_alta_vendedora'), {
                'username': 'vendedora_nueva', 'password': 'una-clave-larga-123',
                'nombre': 'Nueva Vendedora', 'codigo': 'nueva10',
            })
        self.assertEqual(response.status_code, 302)
        nuevo = get_user_model().objects.get(username='vendedora_nueva')
        self.assertTrue(nuevo.groups.filter(name='Vendedora').exists())
        self.assertFalse(nuevo.groups.filter(name='Jefe').exists())
        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=nuevo, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        ).exists())
        # bookings.Vendedora lleva RLS: para verla desde el test hace falta alcance.
        with scope.con_empresa(self.empresa):
            self.assertTrue(
                Vendedora.objects.filter(usuario=nuevo, empresa=self.empresa, codigo='nueva10').exists()
            )

    def test_username_repetido_da_error_de_formulario_no_500(self):
        get_user_model().objects.create_user('ya_existe', password='x')
        self.client.force_login(self.jefe)
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            response = self.client.post(reverse('admin:bookings_user_dar_de_alta_vendedora'), {
                'username': 'ya_existe', 'password': 'una-clave-larga-123',
                'nombre': 'Nueva', 'codigo': 'otro10',
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una cuenta')


class RutasPublicasEmpresaTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa(slug='empresa-cupo', nombre='Cupo')
        crear_flota(self.empresa)

    def test_responde_para_slug_valido(self):
        response = self.client.get(
            reverse('cupo', kwargs={'empresa_slug': self.empresa.slug}),
            {'fecha': (date.today() + timedelta(days=5)).isoformat()},
        )
        self.assertEqual(response.status_code, 200)

    def test_404_si_empresa_no_existe(self):
        response = self.client.get(
            reverse('cupo', kwargs={'empresa_slug': 'no-existe'}),
            {'fecha': (date.today() + timedelta(days=5)).isoformat()},
        )
        self.assertEqual(response.status_code, 404)

    def test_404_si_empresa_pausada(self):
        pausada = crear_empresa(slug='empresa-pausada', nombre='Pausada', activo=False)
        response = self.client.get(
            reverse('cupo', kwargs={'empresa_slug': pausada.slug}),
            {'fecha': (date.today() + timedelta(days=5)).isoformat()},
        )
        self.assertEqual(response.status_code, 404)


class ArmarPanoramaEmpresaTests(OperadorTestCase):
    def test_panorama_no_mezcla_pangas_de_otra_empresa(self):
        empresa_a = crear_empresa(slug='empresa-a9', nombre='A9')
        empresa_b = crear_empresa(slug='empresa-b9', nombre='B9')
        crear_flota(empresa_a, composicion=[(1, 3)])
        crear_flota(empresa_b, composicion=[(2, 3)])

        panorama = armar_panorama(date.today(), empresa_a)
        self.assertEqual(len(panorama.renglones), 1)


class SerializerEmpresaTests(OperadorTestCase):
    def test_extras_de_otra_empresa_no_pasan_el_checkout(self):
        from rest_framework.test import APIRequestFactory

        from .serializers import ReservaCheckoutSerializer

        empresa_a = crear_empresa(slug='empresa-a10', nombre='A10')
        empresa_b = crear_empresa(slug='empresa-b10', nombre='B10')
        crear_flota(empresa_a)
        extra_b = ExtrasItem.objects.create(
            empresa=empresa_b, tipo=ExtrasItem.Tipo.BRUNCH, nombre='Brunch', precio=Decimal('100'), activo=True,
        )

        factory = APIRequestFactory()
        request = factory.post('/api/empresa-a10/reservas/')
        serializer = ReservaCheckoutSerializer(data={
            'checkout_id': str(uuid.uuid4()),
            'fecha': (date.today() + timedelta(days=8)).isoformat(),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'extras': [{'id': extra_b.pk}],
        }, context={'request': request, 'empresa': empresa_a})

        self.assertFalse(serializer.is_valid())
        self.assertIn('extras', serializer.errors)


class ComandosEmpresaTests(TestCase):
    def test_limpiar_checkouts_no_cuenta_doble_entre_empresas(self):
        empresa_a = crear_empresa(slug='empresa-a11', nombre='A11')
        crear_empresa(slug='empresa-b11', nombre='B11')  # sin checkouts viejos
        vieja = crear_reserva(empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO)
        with scope.con_empresa(empresa_a):
            Reserva.objects.filter(pk=vieja.pk).update(creado_en=timezone.now() - timedelta(days=40))

        out = StringIO()
        call_command('limpiar_checkouts_abandonados', '--dry-run', stdout=out)

        self.assertIn('Se borrarian 1 checkout', out.getvalue())

    def test_revisar_cupo_no_mezcla_reservas_de_otra_empresa(self):
        empresa_a = crear_empresa(slug='empresa-a12', nombre='A12')
        empresa_b = crear_empresa(slug='empresa-b12', nombre='B12')
        crear_flota(empresa_a, composicion=[(1, 3)])
        crear_flota(empresa_b, composicion=[(1, 3)])
        fecha = date.today() + timedelta(days=30)

        # Dos reservas del mismo dia, cada una en su propia Empresa: cada una
        # cabe sola en su unica panga de 3. Si se mezclaran, "2 viajes
        # vendidos" contra 1 sola panga marcaria un falso problema.
        crear_reserva(empresa_a, fecha=fecha, numero_personas=3, estado=Reserva.Estado.PAGADA)
        crear_reserva(empresa_b, fecha=fecha, numero_personas=3, estado=Reserva.Estado.PAGADA)

        out = StringIO()
        call_command('revisar_cupo', stdout=out)
        self.assertNotIn('No cierra', out.getvalue())


class AvisoAsignacionRescopeTests(TestCase):
    def test_avisa_dentro_del_alcance_reabierto(self):
        empresa = crear_empresa(slug='empresa-aviso', nombre='Aviso')
        with scope.con_empresa(empresa):
            crear_flota(empresa)
            embarcacion = Embarcacion.objects.filter(empresa=empresa).first()
            capitan = Capitan.objects.create(empresa=empresa, nombre='Cap', telefono='6120000000')

            with mock.patch('apps.bookings.signals.enviar_correo_asignacion', return_value=True) as enviar_mock:
                with self.captureOnCommitCallbacks(execute=True):
                    reserva = Reserva.objects.create(**datos_reserva(
                        empresa, estado=Reserva.Estado.PAGADA, embarcacion=embarcacion, capitan=capitan,
                    ))

            enviar_mock.assert_called_once()
            reserva.refresh_from_db()
            self.assertIsNotNone(reserva.aviso_asignacion_enviado_en)
