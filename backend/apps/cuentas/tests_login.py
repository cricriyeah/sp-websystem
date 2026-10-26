"""Turnstile en el inicio de sesion del backoffice (apps/cuentas/login.py) y avisos de Django como tarjetas."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import constants as niveles
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

CAPTCHA = 'apps.cuentas.login.verificar_turnstile_obligatorio'
CON_LLAVES = dict(TURNSTILE_SECRET_KEY='secreto', TURNSTILE_SITE_KEY='llave-publica', LOGIN_TURNSTILE_OBLIGATORIO=True)


class LoginConTurnstileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'una-clave-larga-123'
        cls.usuario = get_user_model().objects.create_user(
            'mostrador', password=cls.password, is_staff=True, email='mostrador@example.com')

    def _entrar(self, token=None, password=None):
        datos = {'username': 'mostrador', 'password': password or self.password}
        if token is not None:
            datos['cf-turnstile-response'] = token
        return self.client.post(reverse('admin:login'), datos)

    def _hay_sesion(self):
        return '_auth_user_id' in self.client.session

    @override_settings(TURNSTILE_SECRET_KEY='', TURNSTILE_SITE_KEY='')
    def test_sin_llaves_no_se_exige_captcha(self):
        with mock.patch(CAPTCHA) as verificar:
            respuesta = self._entrar()

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self._hay_sesion())
        verificar.assert_not_called()

    @override_settings(**CON_LLAVES)
    def test_con_llaves_y_sin_token_no_se_entra_aunque_la_clave_sea_buena(self):
        with mock.patch(CAPTCHA, return_value=False) as verificar:
            respuesta = self._entrar()

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_sesion())
        self.assertContains(respuesta, 'No pudimos comprobar que eres una persona')
        verificar.assert_called_once()

    @override_settings(**CON_LLAVES)
    def test_un_captcha_malo_ni_siquiera_prueba_la_contrasena(self):
        with mock.patch(CAPTCHA, return_value=False), \
                mock.patch('django.contrib.auth.forms.authenticate') as autenticar:
            self._entrar(token='x', password='cualquiera')

        autenticar.assert_not_called()

    @override_settings(**CON_LLAVES)
    def test_con_token_valido_entra_y_se_verifica_la_accion_login_y_el_hostname(self):
        with mock.patch(CAPTCHA, return_value=True) as verificar:
            respuesta = self._entrar(token='token-bueno')

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self._hay_sesion())
        args, kwargs = verificar.call_args
        self.assertEqual(args[0], 'token-bueno')
        self.assertEqual(kwargs['accion'], 'login')
        self.assertEqual(kwargs['hostname'], 'testserver')

    @override_settings(**CON_LLAVES)
    def test_con_token_valido_pero_clave_mala_no_entra(self):
        with mock.patch(CAPTCHA, return_value=True):
            respuesta = self._entrar(token='token-bueno', password='mala-mala-123')

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_sesion())

    @override_settings(**{**CON_LLAVES, 'LOGIN_TURNSTILE_OBLIGATORIO': False})
    def test_la_salida_de_emergencia_deja_entrar_sin_captcha(self):
        with mock.patch(CAPTCHA) as verificar:
            respuesta = self._entrar()

        self.assertEqual(respuesta.status_code, 302)
        verificar.assert_not_called()

    @override_settings(**CON_LLAVES)
    def test_la_pantalla_pinta_el_widget_del_login_con_su_llave(self):
        respuesta = self.client.get(reverse('admin:login'))

        self.assertContains(respuesta, 'id="login-turnstile"')
        self.assertContains(respuesta, 'data-sitekey="llave-publica"')
        self.assertContains(respuesta, 'tenancy/login-turnstile.js')
        self.assertContains(respuesta, 'render=explicit&onload=cargaTurnstileLogin')

    @override_settings(TURNSTILE_SECRET_KEY='', TURNSTILE_SITE_KEY='')
    def test_sin_llaves_la_pantalla_no_carga_nada_de_cloudflare(self):
        respuesta = self.client.get(reverse('admin:login'))

        self.assertNotContains(respuesta, 'login-turnstile')
        self.assertNotContains(respuesta, 'challenges.cloudflare.com')

    @override_settings(**CON_LLAVES)
    def test_un_token_del_checkout_no_sirve_aqui(self):
        # El verificador real compara `action`: uno emitido para otra accion se rechaza.
        respuesta_cloudflare = mock.Mock(status_code=200)
        respuesta_cloudflare.json.return_value = {'success': True, 'action': 'checkout', 'hostname': 'testserver'}
        with mock.patch('apps.bookings.captcha._consultar_siteverify', return_value=respuesta_cloudflare):
            respuesta = self._entrar(token='token-del-checkout')

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self._hay_sesion())


class TopeDeCaptchasRechazadosTests(TestCase):
    """Un captcha rechazado no cuenta en Axes: tiene su propio tope por IP y no llama a Cloudflare al pasarse."""

    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user('mostrador', password='una-clave-larga-123', is_staff=True)

    def _entrar(self):
        return self.client.post(
            reverse('admin:login'), {'username': 'mostrador', 'password': 'una-clave-larga-123'})

    @override_settings(**CON_LLAVES, LOGIN_MAX_CAPTCHA_FALLIDOS_IP_HORA=2)
    def test_pasado_el_tope_se_rechaza_sin_llamar_a_cloudflare(self):
        from .models import EventoRecuperacion

        with mock.patch(CAPTCHA, return_value=False) as verificar:
            self._entrar()
            self._entrar()
            self.assertEqual(verificar.call_count, 2)
            respuesta = self._entrar()

        self.assertEqual(verificar.call_count, 2)  # el tercero ni llego a Cloudflare
        self.assertContains(respuesta, 'Demasiados intentos')
        self.assertEqual(EventoRecuperacion.objects.filter(tipo='login_captcha').count(), 2)

    @override_settings(**CON_LLAVES, LOGIN_MAX_CAPTCHA_FALLIDOS_IP_HORA=2)
    def test_los_captchas_viejos_no_cuentan(self):
        from datetime import timedelta

        from django.utils import timezone

        from .models import EventoRecuperacion

        for _ in range(5):
            EventoRecuperacion.objects.create(
                tipo='login_captcha', resultado='rechazado', correo_hash='', ip='127.0.0.1',
                creado_en=timezone.now() - timedelta(hours=2))

        with mock.patch(CAPTCHA, return_value=True):
            respuesta = self._entrar()

        self.assertEqual(respuesta.status_code, 302)

    @override_settings(**CON_LLAVES, LOGIN_TURNSTILE_TIMEOUT_SEGUNDOS=3)
    def test_la_espera_a_cloudflare_es_corta(self):
        with mock.patch(CAPTCHA, return_value=True) as verificar:
            self._entrar()

        self.assertEqual(verificar.call_args.kwargs['timeout'], 3)


class AvisosDeArranqueTests(SimpleTestCase):
    def _avisos(self, **ajustes):
        from .checks import login_sin_turnstile

        with override_settings(DEBUG=False, **ajustes):
            return [m.id for m in login_sin_turnstile(None)]

    def test_sin_llaves_avisa(self):
        self.assertEqual(self._avisos(TURNSTILE_SECRET_KEY='', TURNSTILE_SITE_KEY=''), ['cuentas.I001'])

    def test_con_la_salida_de_emergencia_avisa(self):
        self.assertEqual(self._avisos(**{**CON_LLAVES, 'LOGIN_TURNSTILE_OBLIGATORIO': False}), ['cuentas.I002'])

    def test_todo_en_orden_no_avisa(self):
        self.assertEqual(self._avisos(**CON_LLAVES), [])

    def test_son_informativos_para_no_romper_check_deploy_en_ci(self):
        from django.core import checks

        from .checks import login_sin_turnstile

        with override_settings(DEBUG=False, TURNSTILE_SECRET_KEY='', TURNSTILE_SITE_KEY=''):
            self.assertTrue(all(m.level < checks.WARNING for m in login_sin_turnstile(None)))


class AvisosDeDjangoComoTarjetasTests(SimpleTestCase):
    """Los mensajes de Django ya no salen como barras: van en un bloque que avisos.js convierte en tarjetas."""

    def _pintar(self, *mensajes):
        return render_to_string(
            'unfold/helpers/messages.html',
            {'messages': list(mensajes), 'DEFAULT_MESSAGE_LEVELS': niveles.DEFAULT_LEVELS},
        )

    def test_cada_mensaje_lleva_su_nivel_para_el_script(self):
        html = self._pintar(Message(niveles.SUCCESS, 'Todo bien'), Message(niveles.ERROR, 'Algo fallo'))

        self.assertIn('data-avisos-django', html)
        self.assertIn('data-nivel="success"', html)
        self.assertIn('data-nivel="error"', html)
        self.assertIn('Todo bien', html)
        self.assertIn('Algo fallo', html)

    def test_el_texto_entra_escapado(self):
        html = self._pintar(Message(niveles.WARNING, '<script>alert(1)</script> Ana'))

        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_sin_mensajes_no_pinta_nada(self):
        self.assertNotIn('data-avisos-django', self._pintar())


class AvisosEstaticosTests(SimpleTestCase):
    """El JS no se puede ejercer sin navegador: se vigilan sus reglas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from pathlib import Path

        estaticos = Path(__file__).resolve().parent.parent / 'tenancy' / 'static' / 'tenancy'
        cls.js = (estaticos / 'avisos.js').read_text(encoding='utf-8')
        cls.css = (estaticos / 'avisos.css').read_text(encoding='utf-8')
        cls.login_js = (estaticos / 'login-turnstile.js').read_text(encoding='utf-8')

    def test_los_avisos_de_django_se_convierten_con_textcontent_y_los_errores_no_se_recortan(self):
        self.assertIn('convertirAvisosDeDjango', self.js)
        self.assertIn("getAttribute('data-nivel') !== 'error'", self.js)
        for prohibido in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write'):
            self.assertNotIn(prohibido, self.js)

    def test_el_bloque_de_barras_se_oculta_en_css_y_el_script_lo_vuelve_a_mostrar_si_falla(self):
        self.assertIn('.avisos-js [data-avisos-django]', self.css)
        self.assertIn("classList.add('avisos-js')", self.js)
        self.assertIn("lista.style.display = 'block'", self.js)

    def test_el_sonido_respeta_el_bloqueo_del_navegador_y_el_boton_de_apagado(self):
        self.assertIn("audio.state !== 'running'", self.js)
        self.assertIn('localStorage', self.js)
        self.assertIn('aviso-sonido', self.css)

    def test_el_widget_del_login_se_renderiza_con_la_accion_login(self):
        self.assertIn("action: 'login'", self.login_js)
        self.assertIn('cargaTurnstileLogin', self.login_js)
