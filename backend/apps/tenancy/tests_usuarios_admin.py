from collections.abc import Iterable
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import scope
from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class UsuariosAdminIntegrationTests(TestCase):
    """Pruebas de alcance, edición y cambio de contraseñas de usuarios usando el
    UserAdmin REAL registrado en apps/bookings/admin.py (con el UserChangeForm
    de Unfold) a través del test client HTTP de Django."""

    def _armar_post_data(self, resp, **overrides):
        """Construye un diccionario de datos POST a partir del formulario en el
        contexto de la respuesta, preservando campos requeridos (como date_joined
        en formato SplitDateTime) y aplicando las modificaciones indicadas."""
        form = resp.context['adminform'].form
        data = {}
        for name, field in form.fields.items():
            val = form[name].value()
            if hasattr(field.widget, 'decompress'):
                parts = field.widget.decompress(val)
                for i, part in enumerate(parts):
                    if part is not None:
                        data[f'{name}_{i}'] = str(part)
            elif isinstance(val, bool):
                if val:
                    data[name] = 'on'
            elif isinstance(val, Iterable) and not isinstance(val, (str, bytes, dict)):
                data[name] = list(val)
            elif val is not None:
                data[name] = val

        for k, v in overrides.items():
            if isinstance(v, bool):
                if v:
                    data[k] = 'on'
                else:
                    data.pop(k, None)
            else:
                data[k] = v

        return data

    def setUp(self):
        call_command('setup_roles', stdout=StringIO())

        sede = Sede.objects.create(nombre='Sede Pruebas Admin', slug='sede-admin-usuarios')
        self.empresa_a = Empresa.objects.create(
            sede=sede, nombre='Empresa A', slug='empresa-admin-a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=sede, nombre='Empresa B', slug='empresa-admin-b',
        )

        # Jefe de Empresa A
        self.jefe_a = User.objects.create_user(
            username='jefe_a', password='password123', email='jefe_a@empresa-a.com', is_staff=True,
        )
        self.jefe_a.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(
            user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )

        # Otro Jefe de Empresa A
        self.otro_jefe_a = User.objects.create_user(
            username='otro_jefe_a', password='password123', email='otro_jefe@empresa-a.com', is_staff=True,
        )
        self.otro_jefe_a.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(
            user=self.otro_jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )

        # Vendedora de Empresa A
        self.vendedora_a = User.objects.create_user(
            username='vendedora_a', password='password123', email='vendedora_a@empresa-a.com', is_staff=True,
        )
        self.vendedora_a.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=self.vendedora_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        # Vendedora de Empresa B
        self.vendedora_b = User.objects.create_user(
            username='vendedora_b', password='password123', email='vendedora_b@empresa-b.com', is_staff=True,
        )
        self.vendedora_b.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=self.vendedora_b, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        # Operador de Plataforma (sin membresía de empresa)
        self.operador = User.objects.create_user(
            username='operador', password='password123', email='operador@plataforma.com', is_staff=True,
        )
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

    def test_jefe_abre_a_su_vendedora_200(self):
        """Un jefe puede abrir la ficha de una vendedora de su empresa (HTTP 200, sin KeyError 500)."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_change', args=[self.vendedora_a.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Puede editar nombre, correo y estado activo/inactivo de su vendedora
        post_data = self._armar_post_data(
            resp,
            first_name='Nombre Nuevo',
            last_name='Apellido Nuevo',
            email='nuevo_correo@empresa-a.com',
            is_active=True,
        )
        resp_post = self.client.post(url, post_data)
        self.assertEqual(resp_post.status_code, 302)
        self.vendedora_a.refresh_from_db()
        self.assertEqual(self.vendedora_a.first_name, 'Nombre Nuevo')
        self.assertEqual(self.vendedora_a.last_name, 'Apellido Nuevo')
        self.assertEqual(self.vendedora_a.email, 'nuevo_correo@empresa-a.com')

    def test_jefe_abre_a_otro_jefe_solo_lectura_o_403_nunca_500(self):
        """Un jefe ve a otro jefe de su empresa pero no puede editarlo: solo lectura (200) o 403, nunca 500."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_change', args=[self.otro_jefe_a.pk])
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (200, 403))
        self.assertNotEqual(resp.status_code, 500)

        # Al intentar guardar cambios sobre otro jefe, se rechaza con 403 (PermissionDenied)
        resp_post = self.client.post(url, {
            'username': self.otro_jefe_a.username,
            'first_name': 'Intento Modificar',
            'email': 'modificado@empresa-a.com',
        })
        self.assertEqual(resp_post.status_code, 403)
        self.otro_jefe_a.refresh_from_db()
        self.assertNotEqual(self.otro_jefe_a.first_name, 'Intento Modificar')

    def test_jefe_abre_a_un_operador_404_o_403(self):
        """Un jefe no tiene en alcance a los operadores de plataforma (302 redirect al índice, 403 o 404)."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_change', args=[self.operador.pk])
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403, 404))
        self.assertNotEqual(resp.status_code, 200)

        # Siguiendo el redirect no revela datos del operador
        resp_follow = self.client.get(url, follow=True)
        self.assertNotContains(resp_follow, self.operador.email)

    def test_vendedora_abre_su_perfil_200_y_el_de_otra_vendedora_404_o_403(self):
        """Una vendedora solo puede abrir su propio perfil (200); usuarios ajenos dan redirect (302), 403 o 404."""
        self.client.force_login(self.vendedora_a)

        # Su propio perfil
        url_propio = reverse('admin:auth_user_change', args=[self.vendedora_a.pk])
        resp_propio = self.client.get(url_propio)
        self.assertEqual(resp_propio.status_code, 200)

        # Otra vendedora
        url_otra = reverse('admin:auth_user_change', args=[self.vendedora_b.pk])
        resp_otra = self.client.get(url_otra)
        self.assertIn(resp_otra.status_code, (302, 403, 404))
        self.assertNotEqual(resp_otra.status_code, 200)
        resp_otra_follow = self.client.get(url_otra, follow=True)
        self.assertNotContains(resp_otra_follow, self.vendedora_b.email)

        # Un jefe
        url_jefe = reverse('admin:auth_user_change', args=[self.jefe_a.pk])
        resp_jefe = self.client.get(url_jefe)
        self.assertIn(resp_jefe.status_code, (302, 403, 404))
        self.assertNotEqual(resp_jefe.status_code, 200)
        resp_jefe_follow = self.client.get(url_jefe, follow=True)
        self.assertNotContains(resp_jefe_follow, self.jefe_a.email)

    def test_jefe_cambia_password_de_su_vendedora_302(self):
        """Un jefe puede cambiar la contraseña de su vendedora vía admin:auth_user_password_change."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_password_change', args=[self.vendedora_a.pk])
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 200)

        resp_post = self.client.post(url, {
            'password1': 'NuevaPasswordVendedora999!',
            'password2': 'NuevaPasswordVendedora999!',
        })
        self.assertEqual(resp_post.status_code, 302)
        self.vendedora_a.refresh_from_db()
        self.assertTrue(self.vendedora_a.check_password('NuevaPasswordVendedora999!'))

    def test_jefe_no_cambia_password_de_otro_jefe(self):
        """Un jefe NO puede cambiar la contraseña de otro jefe (HTTP 403)."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_password_change', args=[self.otro_jefe_a.pk])
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 403)

        resp_post = self.client.post(url, {
            'password1': 'PasswordHacker999!',
            'password2': 'PasswordHacker999!',
        })
        self.assertEqual(resp_post.status_code, 403)
        self.otro_jefe_a.refresh_from_db()
        self.assertFalse(self.otro_jefe_a.check_password('PasswordHacker999!'))

    def test_jefe_no_cambia_password_de_operador(self):
        """Un jefe NO puede cambiar la contraseña de un operador (404 o 403)."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_password_change', args=[self.operador.pk])
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (403, 404))

    def test_operador_cambia_a_todos(self):
        """El operador de plataforma puede abrir, editar campos y cambiar la contraseña de cualquier usuario."""
        self.client.force_login(self.operador)

        for u in [self.jefe_a, self.otro_jefe_a, self.vendedora_a, self.vendedora_b]:
            url_change = reverse('admin:auth_user_change', args=[u.pk])
            resp_change = self.client.get(url_change)
            self.assertEqual(resp_change.status_code, 200)

            # POST de cambio de usuario: operador edita los datos de cualquier usuario
            nuevo_nombre = f'Nombre Editado {u.username}'
            post_data = self._armar_post_data(resp_change, first_name=nuevo_nombre)
            resp_post = self.client.post(url_change, post_data)
            self.assertEqual(resp_post.status_code, 302)
            u.refresh_from_db()
            self.assertEqual(u.first_name, nuevo_nombre)

            # POST de cambio de contraseña: operador cambia la contraseña de cualquier usuario
            url_pwd = reverse('admin:auth_user_password_change', args=[u.pk])
            resp_pwd = self.client.post(url_pwd, {
                'password1': 'PasswordOperadorGlobal123!',
                'password2': 'PasswordOperadorGlobal123!',
            })
            self.assertEqual(resp_pwd.status_code, 302)
            u.refresh_from_db()
            self.assertTrue(u.check_password('PasswordOperadorGlobal123!'))

    def test_jefe_contiene_todos_los_permisos_de_vendedora_y_operador_los_de_jefe(self):
        """El grupo Jefe debe ser superconjunto de Vendedora, y OperadorPlataforma de Jefe."""
        grupo_vend = Group.objects.get(name='Vendedora')
        grupo_jefe = Group.objects.get(name='Jefe')
        grupo_op = Group.objects.get(name='OperadorPlataforma')

        perms_vend = set(grupo_vend.permissions.values_list('codename', flat=True))
        perms_jefe = set(grupo_jefe.permissions.values_list('codename', flat=True))
        perms_op = set(grupo_op.permissions.values_list('codename', flat=True))

        self.assertTrue(perms_vend.issubset(perms_jefe))
        self.assertTrue(perms_jefe.issubset(perms_op))

        # Vendedora debe tener view y change sobre auth.user
        self.assertIn('view_user', perms_vend)
        self.assertIn('change_user', perms_vend)

    def test_usuario_no_puede_desactivarse_a_si_mismo(self):
        """Un usuario no puede desactivar su propia cuenta en el formulario de admin."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_change', args=[self.jefe_a.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Enviar POST sin is_active (o con is_active apagado)
        post_data = self._armar_post_data(resp, is_active=False)
        self.client.post(url, post_data)
        self.jefe_a.refresh_from_db()
        self.assertTrue(self.jefe_a.is_active)

    def test_nadie_salvo_operador_puede_borrar_usuarios(self):
        """has_delete_permission bloquea el borrado de usuarios a cualquier rol salvo el operador."""
        url_delete_vendedora = reverse('admin:auth_user_delete', args=[self.vendedora_a.pk])

        # Jefe no puede borrar
        self.client.force_login(self.jefe_a)
        resp_jefe = self.client.get(url_delete_vendedora)
        self.assertEqual(resp_jefe.status_code, 403)
        resp_post_jefe = self.client.post(url_delete_vendedora, {'post': 'yes'})
        self.assertEqual(resp_post_jefe.status_code, 403)

        # Vendedora no puede borrar
        self.client.force_login(self.vendedora_a)
        resp_vend = self.client.get(url_delete_vendedora)
        self.assertEqual(resp_vend.status_code, 403)

        # Operador sí puede borrar a otros usuarios
        self.client.force_login(self.operador)
        resp_op_get = self.client.get(url_delete_vendedora)
        self.assertEqual(resp_op_get.status_code, 200)

        # Operador no puede borrarse a sí mismo
        url_delete_op = reverse('admin:auth_user_delete', args=[self.operador.pk])
        resp_op_self = self.client.get(url_delete_op)
        self.assertEqual(resp_op_self.status_code, 403)

    def test_vendedora_changelist_muestra_solo_a_si_misma(self):
        """En el listado de usuarios, la vendedora ve únicamente su propia fila."""
        self.client.force_login(self.vendedora_a)
        url = reverse('admin:auth_user_changelist')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.vendedora_a.username)
        self.assertNotContains(resp, self.jefe_a.username)
        self.assertNotContains(resp, self.otro_jefe_a.username)
        self.assertNotContains(resp, self.vendedora_b.username)

    def test_jefe_changelist_muestra_usuarios_de_su_empresa_no_de_otra(self):
        """En el listado de usuarios, el jefe ve a los miembros de su empresa y no a los de otra."""
        self.client.force_login(self.jefe_a)
        url = reverse('admin:auth_user_changelist')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.jefe_a.username)
        self.assertContains(resp, self.otro_jefe_a.username)
        self.assertContains(resp, self.vendedora_a.username)
        self.assertNotContains(resp, self.vendedora_b.username)
        self.assertNotContains(resp, self.operador.username)

    def test_jefe_no_toma_cuenta_con_membresia_en_otra_empresa(self):
        """Una vendedora con membresía en A y en B no la edita ni le cambia la contraseña el jefe de A."""
        MembresiaEmpresa.objects.create(
            user=self.vendedora_a, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        self.client.force_login(self.jefe_a)
        url_pw = reverse('admin:auth_user_password_change', args=[self.vendedora_a.pk])
        self.assertEqual(self.client.get(url_pw).status_code, 403)
        resp = self.client.post(url_pw, {
            'password1': 'TomaDeCuenta12345!', 'password2': 'TomaDeCuenta12345!',
        })
        self.assertEqual(resp.status_code, 403)
        self.vendedora_a.refresh_from_db()
        self.assertTrue(self.vendedora_a.check_password('password123'))

        url = reverse('admin:auth_user_change', args=[self.vendedora_a.pk])
        resp = self.client.post(url, {'username': 'vendedora_a', 'email': 'robado@evil.com'})
        self.assertNotEqual(resp.status_code, 302)
        self.vendedora_a.refresh_from_db()
        self.assertNotEqual(self.vendedora_a.email, 'robado@evil.com')

    def test_jefe_no_edita_a_un_superusuario_con_membresia_en_su_empresa(self):
        """Un superusuario con membresía en la empresa del jefe no se puede editar desde el jefe."""
        super_u = User.objects.create_user(
            username='super_u', password='password123', is_staff=True, is_superuser=True,
        )
        MembresiaEmpresa.objects.create(
            user=super_u, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        self.client.force_login(self.jefe_a)
        url_pw = reverse('admin:auth_user_password_change', args=[super_u.pk])
        resp = self.client.post(url_pw, {
            'password1': 'TomaDeCuenta12345!', 'password2': 'TomaDeCuenta12345!',
        })
        self.assertEqual(resp.status_code, 403)
        super_u.refresh_from_db()
        self.assertTrue(super_u.check_password('password123'))


class CorreoUnicoEnElAdminDeUsuariosTests(TestCase):
    """El formulario de edicion de Usuarios no deja repetir el correo de otra cuenta (apps/cuentas necesita
    que un correo identifique a una sola cuenta)."""

    def setUp(self):
        from apps.bookings.admin import UserAdmin
        self.formulario = UserAdmin.form
        self.ana = User.objects.create_user(username='ana_correo', email='ana@ejemplo.com', password='PasswordValida123!')
        self.beto = User.objects.create_user(username='beto_correo', email='beto@ejemplo.com', password='PasswordValida123!')

    def limpiar(self, instancia, nuevo_correo):
        form = self.formulario(instance=instancia, data={'email': nuevo_correo})
        form.cleaned_data = {'email': nuevo_correo}
        return form

    def test_rechaza_el_correo_de_otra_cuenta_sin_distinguir_mayusculas(self):
        form = self.limpiar(self.beto, 'ANA@ejemplo.com')
        with self.assertRaises(DjangoValidationError):
            form.clean_email()

    def test_deja_conservar_el_propio_correo(self):
        self.assertEqual(self.limpiar(self.ana, 'ana@ejemplo.com').clean_email(), 'ana@ejemplo.com')

    def test_deja_cambiarlo_a_uno_libre_y_dejarlo_vacio(self):
        self.assertEqual(self.limpiar(self.ana, 'nueva@ejemplo.com').clean_email(), 'nueva@ejemplo.com')
        self.assertEqual(self.limpiar(self.ana, '').clean_email(), '')

    def test_una_cuenta_antigua_con_correo_repetido_se_puede_seguir_editando_sin_tocar_el_correo(self):
        User.objects.filter(pk=self.beto.pk).update(email='ana@ejemplo.com')
        self.beto.refresh_from_db()
        form = self.formulario(instance=self.beto, data={'email': 'ana@ejemplo.com'})
        form.cleaned_data = {'email': 'ana@ejemplo.com'}
        self.assertEqual(form.clean_email(), 'ana@ejemplo.com')

