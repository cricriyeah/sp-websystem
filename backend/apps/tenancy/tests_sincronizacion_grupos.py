# backend/apps/tenancy/tests_sincronizacion_grupos.py
from io import StringIO

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.bookings.admin import UserAdmin
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.tenancy.roles import (
    asegurar_grupo,
    sincronizar_grupos_de_usuario,
    sincronizar_todos,
)
from apps.tenancy.usuarios import crear_usuario_con_rol

User = get_user_model()


def _fecha_ingreso(usuario):
    """Campos de fecha de ingreso que el formulario real del admin manda precargados."""
    return {
        'date_joined_0': usuario.date_joined.date().isoformat(),
        'date_joined_1': usuario.date_joined.time().strftime('%H:%M:%S'),
    }


class SincronizacionGruposSenalesTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())
        self.sede = Sede.objects.create(nombre='Sede Sync', slug='sede-sync-test')
        self.empresa_a = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Sync A', slug='empresa-sync-a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Sync B', slug='empresa-sync-b',
        )
        self.user = User.objects.create_user(username='usuario_prueba', password='x', is_staff=True)

    def test_crear_membresia_jefe_agrega_grupo_jefe_y_no_vendedora(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())
        self.assertFalse(self.user.groups.filter(name='Vendedora').exists())

    def test_cambiar_rol_a_vendedora_mueve_de_jefe_a_vendedora(self):
        membresia = MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())

        membresia.rol = MembresiaEmpresa.Rol.VENDEDORA
        membresia.save()

        self.assertFalse(self.user.groups.filter(name='Jefe').exists())
        self.assertTrue(self.user.groups.filter(name='Vendedora').exists())

    def test_borrar_membresia_saca_del_grupo(self):
        membresia = MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())

        membresia.delete()

        self.assertFalse(self.user.groups.filter(name='Jefe').exists())
        self.assertFalse(self.user.groups.filter(name='Vendedora').exists())

    def test_usuario_con_dos_membresias_queda_en_ambos_grupos(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())
        self.assertTrue(self.user.groups.filter(name='Vendedora').exists())

    def test_membresia_con_rol_distinto_al_de_otra_empresa_no_valida(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        mixta = MembresiaEmpresa(
            user=self.user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        with self.assertRaises(ValidationError) as ctx:
            mixta.full_clean()
        self.assertIn('rol', ctx.exception.message_dict)

    def test_membresia_con_el_mismo_rol_en_otra_empresa_valida(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        MembresiaEmpresa(
            user=self.user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.JEFE,
        ).full_clean()

    def test_cambiar_el_rol_de_la_unica_membresia_valida(self):
        membresia = MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        membresia.rol = MembresiaEmpresa.Rol.VENDEDORA
        membresia.full_clean()

    def test_borrar_solo_una_membresia_conserva_el_otro_grupo(self):
        m_jefe = MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        m_vend = MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        m_jefe.delete()

        self.assertFalse(self.user.groups.filter(name='Jefe').exists())
        self.assertTrue(self.user.groups.filter(name='Vendedora').exists())

    def test_borrar_usuario_no_lanza_error(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        # La señal post_delete de MembresiaEmpresa corre durante la cascada de User.delete()
        self.user.delete()
        self.assertFalse(User.objects.filter(username='usuario_prueba').exists())

    def test_usuario_operador_con_membresia_conserva_operador_plataforma(self):
        grupo_op = Group.objects.get(name='OperadorPlataforma')
        self.user.groups.add(grupo_op)

        m = MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        self.assertTrue(self.user.groups.filter(name='OperadorPlataforma').exists())
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())

        m.rol = MembresiaEmpresa.Rol.VENDEDORA
        m.save()
        self.assertTrue(self.user.groups.filter(name='OperadorPlataforma').exists())
        self.assertTrue(self.user.groups.filter(name='Vendedora').exists())
        self.assertFalse(self.user.groups.filter(name='Jefe').exists())

        m.delete()
        self.assertTrue(self.user.groups.filter(name='OperadorPlataforma').exists())
        self.assertFalse(self.user.groups.filter(name='Vendedora').exists())

    def test_sincronizar_grupos_usuario_sin_pk_o_inexistente(self):
        # Usuario no guardado (sin pk)
        u_nuevo = User(username='sin_guardar')
        sincronizar_grupos_de_usuario(u_nuevo)
        # Usuario inexistente
        u_dummy = User(pk=999999)
        sincronizar_grupos_de_usuario(u_dummy)
        # None
        sincronizar_grupos_de_usuario(None)

    def test_sincronizar_todos_arregla_usuario_desincronizado(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        # Desincronizar a mano
        self.user.groups.clear()
        self.assertFalse(self.user.groups.filter(name='Jefe').exists())

        total = sincronizar_todos()
        self.assertGreaterEqual(total, 1)
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())

    def test_sincronizar_todos_no_toca_usuarios_sin_membresia(self):
        # Operador especial sin membresía
        operador_puro = User.objects.create_user(username='operador_puro', password='x')
        grupo_op = Group.objects.get(name='OperadorPlataforma')
        operador_puro.groups.add(grupo_op)

        sincronizar_todos()
        self.assertTrue(operador_puro.groups.filter(name='OperadorPlataforma').exists())

    def test_setup_roles_corre_sincronizar_todos(self):
        MembresiaEmpresa.objects.create(
            user=self.user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )
        self.user.groups.clear()
        self.assertFalse(self.user.groups.filter(name='Jefe').exists())

        call_command('setup_roles', stdout=StringIO())
        self.assertTrue(self.user.groups.filter(name='Jefe').exists())

    def test_crear_usuario_con_rol_asigna_grupo_automaticamente(self):
        with scope.con_empresa(self.empresa_a):
            nuevo_jefe = crear_usuario_con_rol(
                username='jefe_creado',
                password='Password123!',
                nombre='Jefe Creado',
                rol=MembresiaEmpresa.Rol.JEFE,
                empresa=self.empresa_a,
            )
            self.assertTrue(nuevo_jefe.groups.filter(name='Jefe').exists())
            self.assertFalse(nuevo_jefe.groups.filter(name='Vendedora').exists())

            nueva_vend = crear_usuario_con_rol(
                username='vend_creada',
                password='Password123!',
                nombre='Vend Creada',
                rol=MembresiaEmpresa.Rol.VENDEDORA,
                empresa=self.empresa_a,
                codigo_vendedora='VEND-SYNC',
            )
            self.assertTrue(nueva_vend.groups.filter(name='Vendedora').exists())
            self.assertFalse(nueva_vend.groups.filter(name='Jefe').exists())


class UserAdminGroupsReadonlyTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())
        self.sede = Sede.objects.create(nombre='Sede Admin Sync', slug='sede-admin-sync')
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Admin Sync', slug='empresa-admin-sync',
        )

        self.grupo_jefe = Group.objects.get(name='Jefe')
        self.grupo_vendedora = Group.objects.get(name='Vendedora')
        self.grupo_operador = Group.objects.get(name='OperadorPlataforma')

        # Operador de plataforma: sin membresía
        self.operador = User.objects.create_user(username='operador_admin', password='x', is_staff=True)
        self.operador.groups.add(self.grupo_operador)

        # Jefe de empresa
        self.jefe = User.objects.create_user(username='jefe_admin', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(
            user=self.jefe, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE,
        )

        # Vendedora de empresa
        self.vendedora = User.objects.create_user(
            username='vendedora_admin', password='x', is_staff=True, email='vendedora@test.com',
        )
        MembresiaEmpresa.objects.create(
            user=self.vendedora, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        self.admin = UserAdmin(User, AdminSite())

    def test_groups_en_readonly_fields_para_operador_jefe_y_vendedora(self):
        factory = RequestFactory()

        req_op = factory.get('/')
        req_op.user = self.operador
        self.assertIn('groups', self.admin.get_readonly_fields(req_op, self.vendedora))

        req_jefe = factory.get('/')
        req_jefe.user = self.jefe
        self.assertIn('groups', self.admin.get_readonly_fields(req_jefe, self.vendedora))

        req_vend = factory.get('/')
        req_vend.user = self.vendedora
        self.assertIn('groups', self.admin.get_readonly_fields(req_vend, self.vendedora))

    def test_get_change_view_200_para_operador_jefe_y_vendedora(self):
        url = reverse('admin:auth_user_change', args=[self.vendedora.pk])

        # 1. Operador
        self.client.force_login(self.operador)
        resp_op = self.client.get(url)
        self.assertEqual(resp_op.status_code, 200)

        # 2. Jefe
        self.client.force_login(self.jefe)
        resp_jefe = self.client.get(url)
        self.assertEqual(resp_jefe.status_code, 200)

        # 3. Vendedora (sobre sí misma)
        self.client.force_login(self.vendedora)
        resp_vend = self.client.get(url)
        self.assertEqual(resp_vend.status_code, 200)

    def test_post_change_view_operador_no_modifica_grupos(self):
        self.client.force_login(self.operador)
        url = reverse('admin:auth_user_change', args=[self.vendedora.pk])

        # El operador intenta modificar el usuario e inyectar grupo Jefe
        post_data = {
            'username': self.vendedora.username,
            'first_name': 'Vendedora Operador Mod',
            'last_name': '',
            'email': self.vendedora.email,
            'is_active': 'on',
            'is_staff': 'on',
            'groups': [self.grupo_jefe.pk],
            **_fecha_ingreso(self.vendedora),
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        self.vendedora.refresh_from_db()
        self.assertEqual(self.vendedora.first_name, 'Vendedora Operador Mod')
        # Sigue en Vendedora, NO pasó a Jefe
        self.assertTrue(self.vendedora.groups.filter(name='Vendedora').exists())
        self.assertFalse(self.vendedora.groups.filter(name='Jefe').exists())

    def test_post_change_view_jefe_no_modifica_grupos(self):
        self.client.force_login(self.jefe)
        url = reverse('admin:auth_user_change', args=[self.vendedora.pk])

        post_data = {
            'username': self.vendedora.username,
            'first_name': 'Vendedora Jefe Mod',
            'last_name': '',
            'email': self.vendedora.email,
            'is_active': 'on',
            **_fecha_ingreso(self.vendedora),
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        self.vendedora.refresh_from_db()
        self.assertEqual(self.vendedora.first_name, 'Vendedora Jefe Mod')
        self.assertTrue(self.vendedora.groups.filter(name='Vendedora').exists())
        self.assertFalse(self.vendedora.groups.filter(name='Jefe').exists())

    def test_post_change_view_vendedora_sobre_si_misma_no_modifica_grupos(self):
        self.client.force_login(self.vendedora)
        url = reverse('admin:auth_user_change', args=[self.vendedora.pk])

        post_data = {
            'username': self.vendedora.username,
            'first_name': 'Vendedora Auto Mod',
            'last_name': '',
            'email': 'nuevo_correo@test.com',
            **_fecha_ingreso(self.vendedora),
        }
        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        self.vendedora.refresh_from_db()
        self.assertEqual(self.vendedora.first_name, 'Vendedora Auto Mod')
        self.assertEqual(self.vendedora.email, 'nuevo_correo@test.com')
        self.assertTrue(self.vendedora.groups.filter(name='Vendedora').exists())
        self.assertFalse(self.vendedora.groups.filter(name='Jefe').exists())
