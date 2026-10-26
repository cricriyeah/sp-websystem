"""Las dos pantallas de la recuperacion (`/admin/recuperar/` y `/admin/recuperar/codigo/`).

Lo central: Turnstile obligatorio en ambos pasos (sin el, ni una escritura ni un correo), respuestas
identicas para cualquier correo, y que el codigo no aparezca en ninguna respuesta ni log.
"""
import logging
import re
import threading
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import views
from .models import CodigoRecuperacion, EventoRecuperacion
from .seguridad import hash_correo
from .testing import HASH_RAPIDO, PASSWORD_NUEVA, PASSWORD_VIEJA, crear_usuario

IP = '203.0.113.9'
AJUSTES = dict(
    TURNSTILE_SITE_KEY='site-key-de-prueba', TURNSTILE_SECRET_KEY='secret-de-prueba',
    RESEND_API_KEY='llave-de-prueba', RESEND_FROM='cuentas@ejemplo.com',
)
NEUTRO = 'Si el correo corresponde a una cuenta activa, te enviamos un código de 6 dígitos. Vence en 10 minutos.'
CODIGO_MALO = 'El código es incorrecto o ya venció. Si fallaste varias veces, pide uno nuevo'


def _sin_csrf(respuesta):
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', '', respuesta.content.decode())


def _cabeceras(respuesta):
    # Fecha y caducidad cambian por segundo: comparar eso hacia la prueba inestable.
    ignorar = {'set-cookie', 'date', 'expires', 'last-modified'}
    return {k: v for k, v in respuesta.headers.items() if k.lower() not in ignorar}


@HASH_RAPIDO
@override_settings(**AJUSTES)
class VistasBase(TestCase):
    def setUp(self):
        for ruta, valor in (
            ('apps.cuentas.views.verificar_turnstile_obligatorio', True),
            ('apps.cuentas.servicio.enviar_correo_codigo_recuperacion', True),
            ('apps.cuentas.servicio.enviar_correo_contrasena_cambiada', True),
        ):
            parche = mock.patch(ruta, return_value=valor)
            setattr(self, ruta.rsplit('.', 1)[1], parche.start())
            self.addCleanup(parche.stop)
        self.url_pedir = reverse('admin_password_reset')
        self.url_codigo = reverse('admin_password_reset_codigo')

    def pedir(self, correo, **extra):
        # El correo sale en `on_commit`, que un TestCase (todo dentro de una transaccion) no dispara solo.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                self.url_pedir, {'correo': correo, 'cf-turnstile-response': 'token'}, REMOTE_ADDR=IP, **extra,
            )

    def codigo_enviado(self):
        return self.enviar_correo_codigo_recuperacion.call_args.args[2].revelar()

    def confirmar(self, correo, codigo, password=PASSWORD_NUEVA, repetida=None, token='token'):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url_codigo, {
                'correo': correo, 'codigo': codigo, 'password1': password, 'password2': repetida or password,
                'cf-turnstile-response': token,
            }, REMOTE_ADDR=IP)

    def sin_escrituras(self):
        self.assertEqual(EventoRecuperacion.objects.count(), 0)
        self.assertEqual(CodigoRecuperacion.objects.count(), 0)
        self.enviar_correo_codigo_recuperacion.assert_not_called()


class PantallasTests(VistasBase):
    def test_las_dos_pantallas_cargan_con_el_widget_el_csrf_y_sin_cache(self):
        for url, accion in ((self.url_pedir, 'recuperar_solicitar'), (self.url_codigo, 'recuperar_confirmar')):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                html = respuesta.content.decode()
                self.assertIn('cf-turnstile', html)
                self.assertIn('data-sitekey="site-key-de-prueba"', html)
                self.assertIn(f'data-action="{accion}"', html)
                self.assertIn('challenges.cloudflare.com/turnstile/v0/api.js', html)
                self.assertIn('csrfmiddlewaretoken', html)
                self.assertIn('no-store', respuesta.headers['Cache-Control'])

    def test_el_campo_del_codigo_y_las_contrasenas_traen_sus_atributos(self):
        html = self.client.get(self.url_codigo).content.decode()
        self.assertIn('autocomplete="one-time-code"', html)
        self.assertIn('inputmode="numeric"', html)
        self.assertIn('pattern="[0-9]{6}"', html)
        self.assertEqual(html.count('autocomplete="new-password"'), 2)

    def test_el_login_del_admin_ofrece_el_enlace_de_recuperacion(self):
        html = self.client.get('/admin/login/').content.decode()
        self.assertIn(self.url_pedir, html)
        self.assertEqual(self.url_pedir, '/admin/recuperar/')
        self.assertEqual(self.url_codigo, '/admin/recuperar/codigo/')

    def test_solo_get_y_post(self):
        self.assertEqual(self.client.put(self.url_pedir).status_code, 405)
        self.assertEqual(self.client.delete(self.url_codigo).status_code, 405)

    def test_un_usuario_con_sesion_va_al_inicio_del_admin(self):
        operador = crear_usuario()
        operador.groups.add(Group.objects.get_or_create(name='OperadorPlataforma')[0])
        self.client.force_login(operador)
        for url in (self.url_pedir, self.url_codigo):
            self.assertRedirects(self.client.get(url), reverse('admin:index'), fetch_redirect_response=False)

    def test_las_vistas_marcan_los_parametros_post_como_sensibles(self):
        for vista in (views.solicitar, views.confirmar):
            peticion = RequestFactory().post('/x', {'password1': 'secreto'})
            peticion.user = mock.Mock(is_authenticated=True)
            vista(peticion)
            self.assertEqual(peticion.sensitive_post_parameters, '__ALL__')


class SinConfiguracionTests(VistasBase):
    def test_sin_site_key_secret_o_resend_responde_503_en_ambas_pantallas(self):
        for ajuste in ('TURNSTILE_SITE_KEY', 'TURNSTILE_SECRET_KEY', 'RESEND_API_KEY', 'RESEND_FROM'):
            with self.subTest(ajuste=ajuste), override_settings(**{ajuste: ''}):
                for metodo, url in ((self.client.get, self.url_pedir), (self.client.get, self.url_codigo)):
                    respuesta = metodo(url)
                    self.assertEqual(respuesta.status_code, 503)
                    self.assertIn('pide a tu jefe que cambie tu contraseña', respuesta.content.decode())
                self.assertEqual(self.pedir('a@b.com').status_code, 503)
                self.assertEqual(self.confirmar('a@b.com', '123456').status_code, 503)
        self.sin_escrituras()


class TurnstileObligatorioTests(VistasBase):
    def test_sin_token_o_con_turnstile_falso_responde_400_sin_escribir_ni_enviar(self):
        usuario = crear_usuario()
        self.verificar_turnstile_obligatorio.return_value = False
        for respuesta in (
            self.pedir(usuario.email),
            self.client.post(self.url_pedir, {'correo': usuario.email}, REMOTE_ADDR=IP),
            self.confirmar(usuario.email, '123456'),
            self.confirmar(usuario.email, '123456', token=''),
        ):
            self.assertEqual(respuesta.status_code, 400)
            self.assertIn('No pudimos verificar que eres una persona', respuesta.content.decode())
        self.sin_escrituras()

    def test_cloudflare_caido_tambien_cierra(self):
        """La funcion real, con la red caida: ni siquiera se mockea `verificar_turnstile_obligatorio`."""
        import requests

        from apps.bookings.captcha import verificar_turnstile_obligatorio as real
        usuario = crear_usuario()
        with mock.patch('apps.cuentas.views.verificar_turnstile_obligatorio', real):
            with mock.patch('apps.bookings.captcha.requests.post', side_effect=requests.ConnectionError('caido')):
                with self.assertLogs('apps.bookings.captcha', level='ERROR'):
                    respuesta = self.pedir(usuario.email)
        self.assertEqual(respuesta.status_code, 400)
        self.sin_escrituras()

    def test_se_verifica_con_la_accion_el_hostname_y_la_ip_de_cada_paso(self):
        usuario = crear_usuario()
        self.pedir(usuario.email)
        llamada = self.verificar_turnstile_obligatorio.call_args
        self.assertEqual(llamada.args[:2], ('token', IP))
        self.assertEqual(llamada.kwargs, {'accion': 'recuperar_solicitar', 'hostname': 'testserver'})

        self.confirmar(usuario.email, '123456')
        llamada = self.verificar_turnstile_obligatorio.call_args
        self.assertEqual(llamada.kwargs, {'accion': 'recuperar_confirmar', 'hostname': 'testserver'})

    @override_settings(ALLOWED_HOSTS=['*'])
    def test_el_hostname_se_toma_sin_el_puerto(self):
        self.pedir(crear_usuario().email, HTTP_HOST='api.ejemplo.com:8443')
        self.assertEqual(self.verificar_turnstile_obligatorio.call_args.kwargs['hostname'], 'api.ejemplo.com')


class CsrfTests(VistasBase):
    def test_un_post_sin_csrf_es_403(self):
        cliente = Client(enforce_csrf_checks=True)
        for url in (self.url_pedir, self.url_codigo):
            self.assertEqual(cliente.post(url, {'correo': 'a@b.com', 'cf-turnstile-response': 'token'}).status_code, 403)
        self.sin_escrituras()


class SolicitarVistaTests(VistasBase):
    def test_la_respuesta_es_la_misma_para_existente_inexistente_inactiva_e_inutilizable(self):
        existente = crear_usuario()
        inactiva = crear_usuario(is_active=False)
        inutilizable = crear_usuario(password=None)
        cuentas = [existente.email, f'nadie-{uuid.uuid4().hex[:8]}@ejemplo.com', inactiva.email, inutilizable.email]

        respuestas = []
        for correo in cuentas:
            # El correo tecleado va en el formulario del paso 2: se normaliza para comparar el resto.
            respuesta = self.pedir(correo)
            respuestas.append((
                respuesta.status_code, _sin_csrf(respuesta).replace(correo, 'CORREO'), _cabeceras(respuesta),
            ))

        self.assertEqual(respuestas[0][0], 200)
        self.assertIn(NEUTRO, respuestas[0][1])
        for otra in respuestas[1:]:
            self.assertEqual(otra, respuestas[0])

    def test_un_error_inesperado_del_servicio_se_ve_igual_que_un_exito(self):
        """Sin el try/except de la vista, el middleware de /admin/ redirigiria distinto solo para cuentas reales."""
        normal = self.pedir(crear_usuario().email)
        otro = crear_usuario()
        with mock.patch('apps.cuentas.views.solicitar_codigo', side_effect=RuntimeError('boom con datos')):
            with self.assertLogs('apps.cuentas.views', level='ERROR') as logs:
                con_error = self.pedir(otro.email)
        self.assertEqual(con_error.status_code, normal.status_code)
        self.assertEqual(
            _sin_csrf(con_error).replace(otro.email, 'C'),
            _sin_csrf(normal).replace(self.enviar_correo_codigo_recuperacion.call_args.args[0], 'C'),
        )
        salida = '\n'.join(logs.output)
        self.assertIn('RuntimeError', salida)
        self.assertNotIn('boom con datos', salida)
        self.assertNotIn('Traceback', salida)

    def test_un_correo_mal_escrito_da_error_de_formato_sin_escribir(self):
        respuesta = self.pedir('esto-no-es-un-correo')
        self.assertEqual(respuesta.status_code, 400)
        self.sin_escrituras()

    def test_la_ip_con_demasiadas_solicitudes_recibe_429_sin_consultar_a_cloudflare(self):
        for n in range(10):
            EventoRecuperacion.objects.create(
                tipo=EventoRecuperacion.SOLICITUD, resultado='sin_cuenta', correo_hash=hash_correo(f'x{n}@e.com'),
                ip=IP, creado_en=timezone.now() - timedelta(minutes=5),
            )
        usuario = crear_usuario()
        respuesta = self.pedir(usuario.email)
        self.assertEqual(respuesta.status_code, 429)
        self.verificar_turnstile_obligatorio.assert_not_called()
        self.enviar_correo_codigo_recuperacion.assert_not_called()

    def test_el_429_no_depende_del_correo(self):
        for n in range(10):
            EventoRecuperacion.objects.create(
                tipo=EventoRecuperacion.SOLICITUD, resultado='sin_cuenta', correo_hash=hash_correo(f'x{n}@e.com'),
                ip=IP, creado_en=timezone.now() - timedelta(minutes=5),
            )
        a = self.pedir(crear_usuario().email)
        b = self.pedir('nadie@ejemplo.com')
        self.assertEqual((a.status_code, a.content.decode().count('429')), (b.status_code, b.content.decode().count('429')))

    def test_envia_el_correo_y_muestra_el_paso_dos_con_el_texto_neutro(self):
        usuario = crear_usuario()
        respuesta = self.pedir(usuario.email)
        self.assertContains(respuesta, NEUTRO)
        self.assertContains(respuesta, 'recuperar_confirmar')
        self.enviar_correo_codigo_recuperacion.assert_called_once()


class ConfirmarVistaTests(VistasBase):
    def preparar(self):
        usuario = crear_usuario()
        self.pedir(usuario.email)
        return usuario, self.codigo_enviado()

    def test_exito_redirige_al_login_con_mensaje_y_sin_iniciar_sesion(self):
        usuario, codigo = self.preparar()
        respuesta = self.confirmar(usuario.email, codigo)
        self.assertRedirects(respuesta, reverse('admin:login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(PASSWORD_NUEVA))
        login = self.client.get(reverse('admin:login'))
        self.assertContains(login, 'Tu contraseña cambió')

    def test_codigo_malo_da_400_con_el_texto_unico(self):
        usuario, codigo = self.preparar()
        malo = f'{(int(codigo) + 1) % 10**6:06d}'
        respuesta = self.confirmar(usuario.email, malo)
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, CODIGO_MALO, status_code=400)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(PASSWORD_VIEJA))

    def test_el_fallo_se_ve_igual_para_cuenta_real_y_para_correo_inexistente(self):
        usuario, codigo = self.preparar()
        malo = f'{(int(codigo) + 1) % 10**6:06d}'
        real = self.confirmar(usuario.email, malo)
        inexistente = self.confirmar(f'nadie-{uuid.uuid4().hex[:8]}@ejemplo.com', malo)
        self.assertEqual(real.status_code, inexistente.status_code)
        self.assertEqual(
            re.sub(r'value="[^"]*@[^"]*"', '', _sin_csrf(real)), re.sub(r'value="[^"]*@[^"]*"', '', _sin_csrf(inexistente)),
        )

    def test_contrasena_debil_o_distinta_da_error_de_formulario_sin_gastar_intento(self):
        usuario, codigo = self.preparar()
        debil = self.confirmar(usuario.email, codigo, password='12345678')
        self.assertEqual(debil.status_code, 400)
        distinta = self.confirmar(usuario.email, codigo, repetida='Otra-Clave-7p2&mar')
        self.assertEqual(distinta.status_code, 400)
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 0)

    def test_un_codigo_que_no_son_seis_digitos_se_rechaza_sin_tocar_nada(self):
        usuario, _ = self.preparar()
        for codigo in ('12345', '1234567', 'abcdef', '12 456'):
            with self.subTest(codigo=codigo):
                self.assertEqual(self.confirmar(usuario.email, codigo).status_code, 400)
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 0)

    def test_una_contrasena_enorme_se_rechaza(self):
        usuario, codigo = self.preparar()
        self.assertEqual(self.confirmar(usuario.email, codigo, password='a1B!' * 100).status_code, 400)

    def test_la_ip_con_demasiados_fallos_recibe_429(self):
        for n in range(20):
            EventoRecuperacion.objects.create(
                tipo=EventoRecuperacion.CONFIRMACION, resultado='codigo_incorrecto',
                correo_hash=hash_correo(f'x{n}@e.com'), ip=IP, creado_en=timezone.now() - timedelta(minutes=5),
            )
        respuesta = self.confirmar('a@b.com', '123456')
        self.assertEqual(respuesta.status_code, 429)
        self.verificar_turnstile_obligatorio.assert_not_called()


class NadaSeFiltraTests(VistasBase):
    def test_ninguna_respuesta_ni_log_lleva_el_codigo_ni_el_hash(self):
        usuario = crear_usuario()
        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger('apps.cuentas.prueba').debug('arranque')
            respuestas = [self.client.get(self.url_pedir), self.pedir(usuario.email)]
            codigo = self.codigo_enviado()
            hash_guardado = CodigoRecuperacion.objects.get(usuario=usuario).codigo_hash
            malo = f'{(int(codigo) + 1) % 10**6:06d}'
            respuestas += [self.confirmar(usuario.email, malo), self.confirmar(usuario.email, codigo)]
        todo = '\n'.join(r.content.decode() + str(r.headers) for r in respuestas) + '\n'.join(logs.output)
        self.assertNotIn(codigo, re.sub(r'csrfmiddlewaretoken[^>]*>', '', todo.replace(f'value="{codigo}"', '')))
        self.assertNotIn(hash_guardado, todo)

    def test_los_eventos_de_todo_el_flujo_no_llevan_el_codigo(self):
        usuario = crear_usuario()
        self.pedir(usuario.email)
        codigo = self.codigo_enviado()
        self.confirmar(usuario.email, codigo)
        for evento in EventoRecuperacion.objects.all():
            self.assertNotIn(codigo, ' '.join(str(v) for v in (evento.resultado, evento.correo_hash, evento.ip, evento.tipo)))


class EnvioEnSegundoPlanoTests(VistasBase):
    def test_con_el_modo_hilo_la_vista_no_habla_con_resend_en_el_hilo_de_la_peticion(self):
        usuario = crear_usuario()
        hilos_de_envio = []

        def post_falso(*args, **kwargs):
            hilos_de_envio.append(threading.current_thread())
            respuesta = mock.Mock(status_code=200)
            respuesta.raise_for_status.return_value = None
            return respuesta

        # Con el envio real (no el mock de setUp) para ver donde corre `requests.post`.
        from apps.notifications import services
        with mock.patch('apps.cuentas.servicio.enviar_correo_codigo_recuperacion', services.enviar_correo_codigo_recuperacion), \
                mock.patch('apps.notifications.services.requests.post', side_effect=post_falso), \
                mock.patch('apps.cuentas.envio.sys.argv', ['manage.py', 'runserver']), \
                mock.patch('apps.cuentas.envio.connections'):
            respuesta = self.pedir(usuario.email)  # ya ejecuta los `on_commit`
            for hilo in threading.enumerate():
                if hilo.name == 'cuentas-envio':
                    hilo.join(timeout=10)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(hilos_de_envio), 1)
        self.assertIsNot(hilos_de_envio[0], threading.main_thread())
        self.assertEqual(hilos_de_envio[0].name, 'cuentas-envio')
