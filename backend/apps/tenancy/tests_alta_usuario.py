from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.bookings.models import Vendedora
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.tenancy.usuarios import crear_usuario_con_rol

User = get_user_model()


class AltaUsuarioTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())

        sede = Sede.objects.create(nombre='Sede Test', slug='sede-alta-test')
        self.empresa_a = Empresa.objects.create(
            sede=sede, nombre='Empresa A', slug='empresa-alta-a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=sede, nombre='Empresa B', slug='empresa-alta-b',
        )

        self.operador = User.objects.create_user(
            username='operador_admin', password='PasswordValida123!', is_staff=True,
        )
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

        self.jefe_a = User.objects.create_user(
            username='jefe_alta_a', password='PasswordValida123!', is_staff=True,
        )
        self.jefe_a.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(
            user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        )

        self.vendedora_a = User.objects.create_user(
            username='vendedora_alta_a', password='PasswordValida123!', is_staff=True,
        )
        self.vendedora_a.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=self.vendedora_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        with scope.con_empresa(self.empresa_a):  # Vendedora tiene RLS: sin alcance Postgres rechaza el INSERT
            Vendedora.objects.create(
                usuario=self.vendedora_a, empresa=self.empresa_a, codigo='venda',
            )

        self.vendedora_b = User.objects.create_user(
            username='vendedora_alta_b', password='PasswordValida123!', is_staff=True,
        )
        self.vendedora_b.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=self.vendedora_b, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        with scope.con_empresa(self.empresa_b):
            Vendedora.objects.create(
                usuario=self.vendedora_b, empresa=self.empresa_b, codigo='vendb',
            )

        self.url = reverse('admin:bookings_user_alta_usuario')

    def _vendedoras(self, **filtros):
        """Vendedora tiene RLS: se lee como operador para comprobar lo que dejó el alta, sin alcance de empresa."""
        with scope.como_operador_plataforma():
            return list(Vendedora.objects.filter(**filtros))

    def test_operador_crea_jefe(self):
        """Operador crea Jefe: queda con is_staff, grupo Jefe, membresía JEFE,
        puede entrar y ve su empresa en el admin."""
        self.client.force_login(self.operador)
        resp = self.client.post(self.url, {
            'username': 'nuevo_jefe',
            'nombre': 'Nuevo Jefe A',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'JEFE',
            'empresa': self.empresa_a.pk,
        })
        self.assertEqual(resp.status_code, 302)

        nuevo = User.objects.get(username='nuevo_jefe')
        self.assertTrue(nuevo.is_staff)
        self.assertTrue(nuevo.is_active)
        self.assertEqual(nuevo.first_name, 'Nuevo Jefe A')
        self.assertTrue(nuevo.groups.filter(name='Jefe').exists())

        membresia = MembresiaEmpresa.objects.get(user=nuevo)
        self.assertEqual(membresia.empresa, self.empresa_a)
        self.assertEqual(membresia.rol, MembresiaEmpresa.Rol.JEFE)
        self.assertFalse(self._vendedoras(usuario=nuevo))

        # Puede entrar y ve su empresa
        self.client.force_login(nuevo)
        resp_cl = self.client.get(reverse('admin:auth_user_changelist'))
        self.assertEqual(resp_cl.status_code, 200)
        self.assertContains(resp_cl, 'nuevo_jefe')
        self.assertContains(resp_cl, self.jefe_a.username)
        self.assertNotContains(resp_cl, self.operador.username)
        self.assertNotContains(resp_cl, self.vendedora_b.username)

    def test_operador_crea_vendedora(self):
        """Operador crea Vendedora: queda con grupo Vendedora, membresía VENDEDORA
        y registro bookings.Vendedora con código."""
        self.client.force_login(self.operador)
        resp = self.client.post(self.url, {
            'username': 'nueva_vendedora_b',
            'nombre': 'Nueva Vendedora B',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'VENDEDORA',
            'empresa': self.empresa_b.pk,
            'codigo': 'vendb01',
        })
        self.assertEqual(resp.status_code, 302)

        nuevo = User.objects.get(username='nueva_vendedora_b')
        self.assertTrue(nuevo.is_staff)
        self.assertTrue(nuevo.is_active)
        self.assertTrue(nuevo.groups.filter(name='Vendedora').exists())

        membresia = MembresiaEmpresa.objects.get(user=nuevo)
        self.assertEqual(membresia.empresa, self.empresa_b)
        self.assertEqual(membresia.rol, MembresiaEmpresa.Rol.VENDEDORA)

        vend = self._vendedoras(usuario=nuevo)[0]
        self.assertEqual(vend.empresa, self.empresa_b)
        self.assertEqual(vend.codigo, 'vendb01')

    def test_jefe_crea_vendedora_de_su_empresa_fuerza_empresa_propia(self):
        """Jefe crea Vendedora de su empresa: la empresa viene forzada aunque
        el POST intente enviar otra empresa."""
        self.client.force_login(self.jefe_a)
        resp = self.client.post(self.url, {
            'username': 'vendedora_por_jefe',
            'nombre': 'Vendedora Creada Por Jefe',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'VENDEDORA',
            'empresa': self.empresa_b.pk,  # intento forzar empresa B
            'codigo': 'vjefe01',
        })
        self.assertEqual(resp.status_code, 302)

        nuevo = User.objects.get(username='vendedora_por_jefe')
        membresia = MembresiaEmpresa.objects.get(user=nuevo)
        self.assertEqual(membresia.empresa, self.empresa_a)

        vend = self._vendedoras(usuario=nuevo)[0]
        self.assertEqual(vend.empresa, self.empresa_a)

    def test_jefe_intenta_crear_jefe_rechazado(self):
        """Jefe intenta crear Jefe: rechazado porque el rol Jefe no es válido para él."""
        self.client.force_login(self.jefe_a)
        resp = self.client.post(self.url, {
            'username': 'intento_jefe_a',
            'nombre': 'Intento Otro Jefe',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'JEFE',
            'codigo': 'intjefe',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('rol', resp.context['form'].errors)
        self.assertFalse(User.objects.filter(username='intento_jefe_a').exists())

    def test_vendedora_recibe_403_en_vista_y_no_ve_agregar(self):
        """Vendedora recibe 403 al abrir la vista de alta y no ve el botón Agregar."""
        self.client.force_login(self.vendedora_a)

        resp_get = self.client.get(self.url)
        self.assertEqual(resp_get.status_code, 403)

        resp_post = self.client.post(self.url, {'username': 'hack'})
        self.assertEqual(resp_post.status_code, 403)

        resp_add = self.client.get(reverse('admin:auth_user_add'))
        self.assertEqual(resp_add.status_code, 403)

        resp_cl = self.client.get(reverse('admin:auth_user_changelist'))
        self.assertEqual(resp_cl.status_code, 200)
        self.assertNotContains(resp_cl, reverse('admin:auth_user_add'))
        self.assertNotContains(resp_cl, self.url)

        # El jefe sí ve el botón de Agregar en su changelist
        self.client.force_login(self.jefe_a)
        resp_jefe_cl = self.client.get(reverse('admin:auth_user_changelist'))
        self.assertEqual(resp_jefe_cl.status_code, 200)
        self.assertContains(resp_jefe_cl, reverse('admin:auth_user_add'))

    def test_usuario_repetido_y_password_debil_dan_error_200_no_500(self):
        """Usuario repetido y contraseña débil dan error de formulario (200 con errores, nunca 500)."""
        self.client.force_login(self.operador)

        # 1. Usuario repetido
        resp_rep = self.client.post(self.url, {
            'username': self.jefe_a.username,
            'nombre': 'Duplicado',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'JEFE',
            'empresa': self.empresa_a.pk,
        })
        self.assertEqual(resp_rep.status_code, 200)
        self.assertIn('username', resp_rep.context['form'].errors)

        # 2. Contraseña débil
        resp_pwd = self.client.post(self.url, {
            'username': 'nuevo_usuario_invalido',
            'nombre': 'Invalido',
            'password': '123',
            'email': 'alta@ejemplo.com', 'password_confirm': '123',
            'rol': 'JEFE',
            'empresa': self.empresa_a.pk,
        })
        self.assertEqual(resp_pwd.status_code, 200)
        self.assertIn('password', resp_pwd.context['form'].errors)
        self.assertFalse(User.objects.filter(username='nuevo_usuario_invalido').exists())

    def test_codigo_vendedora_duplicado_da_error(self):
        """Código de vendedora duplicado en la misma empresa da error de formulario."""
        self.client.force_login(self.jefe_a)

        # 'venda' ya existe en empresa A
        resp = self.client.post(self.url, {
            'username': 'vendedora_chocada',
            'nombre': 'Chocada',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'VENDEDORA',
            'codigo': 'venda',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('codigo', resp.context['form'].errors)
        self.assertFalse(User.objects.filter(username='vendedora_chocada').exists())

        # En otra empresa el mismo código sí se permite
        self.client.force_login(self.operador)
        resp_b = self.client.post(self.url, {
            'username': 'vendedora_empresa_b',
            'nombre': 'Vendedora B',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'VENDEDORA',
            'empresa': self.empresa_b.pk,
            'codigo': 'venda',
        })
        self.assertEqual(resp_b.status_code, 302)
        self.assertTrue(self._vendedoras(empresa=self.empresa_b, codigo='venda'))

    def test_get_agregar_usuario_redirige_a_vista_nueva(self):
        """GET a "Sistema > Usuarios > Agregar" redirige a la vista nueva de alta para autorizados."""
        # Operador
        self.client.force_login(self.operador)
        resp_op = self.client.get(reverse('admin:auth_user_add'))
        self.assertRedirects(resp_op, self.url)

        # Jefe
        self.client.force_login(self.jefe_a)
        resp_jefe = self.client.get(reverse('admin:auth_user_add'))
        self.assertRedirects(resp_jefe, self.url)

    def test_sin_grupos_previos_alta_los_crea(self):
        """Sin grupos de roles previos en la base de datos, el alta los crea automáticamente."""
        Group.objects.filter(name__in=['Jefe', 'Vendedora']).delete()
        self.client.force_login(self.operador)

        resp = self.client.post(self.url, {
            'username': 'jefe_sin_grupos_previos',
            'nombre': 'Jefe Nuevo',
            'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!',
            'rol': 'JEFE',
            'empresa': self.empresa_a.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Group.objects.filter(name='Jefe').exists())
        self.assertTrue(Group.objects.filter(name='Vendedora').exists())

        nuevo = User.objects.get(username='jefe_sin_grupos_previos')
        self.assertTrue(nuevo.groups.filter(name='Jefe').exists())

    def test_servicio_crear_usuario_con_rol_directo(self):
        """Pruebas directas de validaciones y comportamiento del servicio crear_usuario_con_rol."""
        # 1. Creación exitosa de Jefe
        jefe = crear_usuario_con_rol(
            username='jefe_servicio',
            password='PasswordValida123!',
            nombre='Jefe Servicio',
            rol=MembresiaEmpresa.Rol.JEFE,
            empresa=self.empresa_a,
        )
        self.assertEqual(jefe.username, 'jefe_servicio')
        self.assertTrue(jefe.groups.filter(name='Jefe').exists())
        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=jefe, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE,
        ).exists())

        # 2. Creación exitosa de Vendedora
        vend = crear_usuario_con_rol(
            username='vend_servicio',
            password='PasswordValida123!',
            nombre='Vend Servicio',
            rol=MembresiaEmpresa.Rol.VENDEDORA,
            empresa=self.empresa_a,
            codigo_vendedora='vendsrv',
        )
        self.assertTrue(vend.groups.filter(name='Vendedora').exists())
        self.assertTrue(self._vendedoras(usuario=vend, empresa=self.empresa_a, codigo='vendsrv'))

        # 3. Rol no válido
        with self.assertRaises(DjangoValidationError):
            crear_usuario_con_rol(
                username='user_rol_malo',
                password='PasswordValida123!',
                nombre='Malo',
                rol='ADMINISTRADOR',
                empresa=self.empresa_a,
            )

        # 4. Usuario repetido
        with self.assertRaises(DjangoValidationError):
            crear_usuario_con_rol(
                username='jefe_servicio',
                password='PasswordValida123!',
                nombre='Otro',
                rol=MembresiaEmpresa.Rol.JEFE,
                empresa=self.empresa_a,
            )

        # 5. Contraseña débil
        with self.assertRaises(DjangoValidationError):
            crear_usuario_con_rol(
                username='user_pwd_debil',
                password='123',
                nombre='Debil',
                rol=MembresiaEmpresa.Rol.JEFE,
                empresa=self.empresa_a,
            )

        # 6. Vendedora sin código
        with self.assertRaises(DjangoValidationError):
            crear_usuario_con_rol(
                username='vend_sin_cod',
                password='PasswordValida123!',
                nombre='Sin Cod',
                rol=MembresiaEmpresa.Rol.VENDEDORA,
                empresa=self.empresa_a,
                codigo_vendedora='',
            )

        # 7. Vendedora con código duplicado en la misma empresa
        with self.assertRaises(DjangoValidationError):
            crear_usuario_con_rol(
                username='vend_cod_dup',
                password='PasswordValida123!',
                nombre='Dup',
                rol=MembresiaEmpresa.Rol.VENDEDORA,
                empresa=self.empresa_a,
                codigo_vendedora='vendsrv',
            )

    def test_grupo_jefe_sin_membresia_de_jefe_no_da_de_alta(self):
        """Estar en el grupo Jefe sin ser JEFE de la empresa (solo vendedora) no da poderes de jefe."""
        raro = User.objects.create_user(username='raro', password='password123', is_staff=True)
        raro.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(
            user=raro, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        self.client.force_login(raro)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        resp = self.client.post(self.url, {
            'username': 'colada', 'nombre': 'Colada', 'password': 'PasswordValida123!',
            'email': 'alta@ejemplo.com', 'password_confirm': 'PasswordValida123!', 'rol': 'VENDEDORA', 'codigo': 'colada1',
        })
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(User.objects.filter(username='colada').exists())


class AltaUsuarioCorreoTests(TestCase):
    """El correo es lo unico que permite recuperar la contrasena (apps/cuentas): sin el, una cuenta nueva
    nacia sin salida. Obligatorio en el formulario del admin, opcional en el servicio, unico en ambos."""

    def setUp(self):
        call_command('setup_roles', stdout=StringIO())
        sede = Sede.objects.create(nombre='Sede Correo', slug='sede-alta-correo')
        self.empresa = Empresa.objects.create(sede=sede, nombre='Empresa Correo', slug='empresa-alta-correo')
        self.operador = User.objects.create_user(username='operador_correo', password='PasswordValida123!', is_staff=True)
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.url = reverse('admin:bookings_user_alta_usuario')

    def datos(self, **extra):
        datos = {
            'username': 'con_correo', 'nombre': 'Con Correo', 'password': 'PasswordValida123!',
            'password_confirm': 'PasswordValida123!', 'rol': 'JEFE', 'empresa': self.empresa.pk,
            'email': 'persona@ejemplo.com',
        }
        datos.update(extra)
        return datos

    def test_servicio_guarda_el_correo_sin_espacios_y_en_minusculas(self):
        nuevo = crear_usuario_con_rol(
            'servicio_correo', 'PasswordValida123!', 'Servicio', 'JEFE', self.empresa, email='  Ana@Ejemplo.COM ',
        )
        self.assertEqual(nuevo.email, 'ana@ejemplo.com')

    def test_servicio_sin_correo_sigue_siendo_valido_para_no_romper_a_quien_ya_lo_llama(self):
        nuevo = crear_usuario_con_rol('servicio_sin_correo', 'PasswordValida123!', 'Servicio', 'JEFE', self.empresa)
        self.assertEqual(nuevo.email, '')

    def test_servicio_rechaza_un_correo_mal_formado(self):
        with self.assertRaises(DjangoValidationError) as contexto:
            crear_usuario_con_rol('mal_correo', 'PasswordValida123!', 'X', 'JEFE', self.empresa, email='no-es-correo')
        self.assertIn('email', contexto.exception.message_dict)
        self.assertFalse(User.objects.filter(username='mal_correo').exists())

    def test_servicio_rechaza_un_correo_repetido_sin_distinguir_mayusculas(self):
        crear_usuario_con_rol('primero', 'PasswordValida123!', 'X', 'JEFE', self.empresa, email='Repetido@Ejemplo.com')
        with self.assertRaises(DjangoValidationError) as contexto:
            crear_usuario_con_rol('segundo', 'PasswordValida123!', 'X', 'JEFE', self.empresa, email='repetido@ejemplo.com')
        self.assertIn('email', contexto.exception.message_dict)
        self.assertFalse(User.objects.filter(username='segundo').exists())

    def test_la_vista_de_alta_guarda_el_correo(self):
        self.client.force_login(self.operador)
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, 302)
        self.assertEqual(User.objects.get(username='con_correo').email, 'persona@ejemplo.com')

    def test_la_vista_de_alta_exige_el_correo(self):
        self.client.force_login(self.operador)
        for correo in ('', 'no-es-correo'):
            with self.subTest(correo=correo):
                resp = self.client.post(self.url, self.datos(email=correo))
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.context['form'].errors.get('email'))
        self.assertFalse(User.objects.filter(username='con_correo').exists())

    def test_la_vista_de_alta_rechaza_un_correo_ya_usado_por_otra_cuenta(self):
        User.objects.create_user(username='otra', email='Persona@Ejemplo.com', password='PasswordValida123!')
        self.client.force_login(self.operador)
        resp = self.client.post(self.url, self.datos())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Ya existe una cuenta con ese correo.', resp.context['form'].errors['email'])
        self.assertFalse(User.objects.filter(username='con_correo').exists())

