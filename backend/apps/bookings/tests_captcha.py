"""Gate anti-bot del checkout (Cloudflare Turnstile).

La ruta que crea reservas es publica y sin autenticacion: el throttle de 20/min
por IP es lo unico que la separa de un bot que rote direcciones y llene el panel
de reservas basura. Ver apps/bookings/captcha.py.
"""
from datetime import date, timedelta
from unittest import mock

import requests
from django.test import override_settings

from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

from .captcha import verificar_turnstile
from .captcha import verificar_turnstile_obligatorio

SECRET = 'secret-de-prueba'


def _respuesta(exito, status=200):
    """Imita la respuesta de siteverify de Cloudflare."""
    respuesta = mock.Mock(status_code=status)
    respuesta.json.return_value = {'success': exito}
    respuesta.raise_for_status.return_value = None
    return respuesta


class VerificarTurnstileTests(ApiTestCase):
    """La funcion de verificacion, aislada de la vista."""

    @override_settings(TURNSTILE_SECRET_KEY='')
    def test_sin_secret_configurado_deja_pasar(self):
        """Mismo patron que Stripe y Resend: sin su variable, la funcion no
        existe para efectos practicos. Asi local y CI no necesitan llaves."""
        with mock.patch('apps.bookings.captcha.requests.post') as post:
            self.assertTrue(verificar_turnstile('lo-que-sea', '1.2.3.4'))
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_token_valido_pasa(self):
        with mock.patch(
            'apps.bookings.captcha.requests.post', return_value=_respuesta(True)
        ) as post:
            self.assertTrue(verificar_turnstile('token-bueno', '1.2.3.4'))

        _, kwargs = post.call_args
        self.assertEqual(kwargs['data']['secret'], SECRET)
        self.assertEqual(kwargs['data']['response'], 'token-bueno')
        self.assertEqual(kwargs['data']['remoteip'], '1.2.3.4')

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_token_rechazado_por_cloudflare_no_pasa(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta(False)):
            self.assertFalse(verificar_turnstile('token-malo', '1.2.3.4'))

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_token_vacio_no_pasa_y_no_gasta_una_llamada(self):
        with mock.patch('apps.bookings.captcha.requests.post') as post:
            self.assertFalse(verificar_turnstile('', '1.2.3.4'))
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_si_cloudflare_no_responde_deja_pasar(self):
        """Decision deliberada: falla abierta.

        Lo que un bot consigue pasando este gate son filas basura en el panel,
        no dinero: crear-pago reusa el PaymentIntent y exige el checkout_id, asi
        que no se pueden generar cobros en masa. Fallar cerrado convertiria una
        caida de Cloudflare en un checkout muerto — eso si cuesta reservas
        reales. El throttle de 20/min por IP sigue puesto debajo, y el fallo se
        registra como error para que Sentry avise.
        """
        with mock.patch(
            'apps.bookings.captcha.requests.post', side_effect=requests.RequestException('timeout')
        ):
            with self.assertLogs('apps.bookings.captcha', level='ERROR'):
                self.assertTrue(verificar_turnstile('token', '1.2.3.4'))


def _respuesta_completa(**campos):
    """Respuesta de siteverify con `action` y `hostname`, como la de un widget real."""
    respuesta = mock.Mock(status_code=200)
    respuesta.json.return_value = {'success': True, 'action': 'recuperar_solicitar', 'hostname': 'api.example.com', **campos}
    respuesta.raise_for_status.return_value = None
    return respuesta


class VerificarTurnstileObligatorioTests(ApiTestCase):
    """La variante FAIL-CLOSED que usa la recuperacion de contrasena.

    A diferencia de `verificar_turnstile` (abierta a proposito para el checkout), aqui todo lo que no
    sea un `True` explicito y completo de Cloudflare es un rechazo.
    """

    def verificar(self, token='token-bueno', **kwargs):
        kwargs.setdefault('accion', 'recuperar_solicitar')
        kwargs.setdefault('hostname', 'api.example.com')
        return verificar_turnstile_obligatorio(token, '1.2.3.4', **kwargs)

    @override_settings(TURNSTILE_SECRET_KEY='')
    def test_sin_secret_rechaza_y_no_llama(self):
        with mock.patch('apps.bookings.captcha.requests.post') as post:
            self.assertFalse(self.verificar())
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_token_vacio_rechaza_sin_llamar(self):
        with mock.patch('apps.bookings.captcha.requests.post') as post:
            self.assertFalse(self.verificar(token=''))
            self.assertFalse(self.verificar(token=None))
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_token_de_mas_de_2048_caracteres_rechaza_sin_llamar(self):
        with mock.patch('apps.bookings.captcha.requests.post') as post:
            self.assertFalse(self.verificar(token='x' * 2049))
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_token_de_2048_caracteres_si_se_consulta(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta_completa()) as post:
            self.assertTrue(self.verificar(token='x' * 2048))
        post.assert_called_once()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_exito_con_action_y_hostname_correctos(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta_completa()) as post:
            self.assertTrue(self.verificar())

        _, kwargs = post.call_args
        self.assertEqual(kwargs['data']['secret'], SECRET)
        self.assertEqual(kwargs['data']['response'], 'token-bueno')
        self.assertEqual(kwargs['data']['remoteip'], '1.2.3.4')
        self.assertEqual(kwargs['timeout'], 5)

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_action_distinta_rechaza(self):
        """Un token generado en el checkout publico (otra accion) no sirve aqui."""
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta_completa(action='checkout')):
            self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_sin_action_en_la_respuesta_rechaza(self):
        respuesta = _respuesta_completa()
        del respuesta.json.return_value['action']
        with mock.patch('apps.bookings.captcha.requests.post', return_value=respuesta):
            self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_hostname_distinto_rechaza(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta_completa(hostname='otro.example.org')):
            self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_success_falso_rechaza(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta_completa(success=False)):
            self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_success_que_no_es_true_estricto_rechaza(self):
        for valor in ('true', 1, 'yes', None):
            with self.subTest(valor=valor):
                with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta_completa(success=valor)):
                    self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_cloudflare_caido_cierra_en_vez_de_dejar_pasar(self):
        """El inverso del checkout: sin respuesta de Cloudflare, no se deja pasar a nadie."""
        for falla in (requests.RequestException('caido'), requests.Timeout('lento')):
            with self.subTest(falla=type(falla).__name__):
                with mock.patch('apps.bookings.captcha.requests.post', side_effect=falla):
                    with self.assertLogs('apps.bookings.captcha', level='ERROR'):
                        self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_http_distinto_de_200_rechaza(self):
        respuesta = _respuesta_completa()
        respuesta.status_code = 500
        with mock.patch('apps.bookings.captcha.requests.post', return_value=respuesta):
            with self.assertLogs('apps.bookings.captcha', level='ERROR'):
                self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_json_invalido_rechaza(self):
        respuesta = _respuesta_completa()
        respuesta.json.side_effect = ValueError('no es json')
        with mock.patch('apps.bookings.captcha.requests.post', return_value=respuesta):
            with self.assertLogs('apps.bookings.captcha', level='ERROR'):
                self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_json_que_no_es_un_objeto_rechaza(self):
        respuesta = _respuesta_completa()
        respuesta.json.return_value = ['success', True]
        with mock.patch('apps.bookings.captcha.requests.post', return_value=respuesta):
            self.assertFalse(self.verificar())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_el_log_de_error_no_lleva_el_token(self):
        token = 'token-secreto-que-no-debe-salir-en-logs'
        with mock.patch('apps.bookings.captcha.requests.post', side_effect=requests.RequestException('caido')):
            with self.assertLogs('apps.bookings.captcha', level='ERROR') as logs:
                self.verificar(token=token)
        self.assertNotIn(token, '\n'.join(logs.output))


class CheckoutConCaptchaTests(ApiTestCase):
    """El gate montado sobre POST /api/reservas/."""

    CHECKOUT_ID = '22222222-2222-4222-8222-222222222222'

    def setUp(self):
        crear_flota(self.empresa)

    def payload(self, **overrides):
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': self.CHECKOUT_ID,
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'USD',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }
        datos.update(overrides)
        return datos

    def enviar(self, **overrides):
        return self.client.post(
            f'/api/{self.empresa.slug}/reservas/', self.payload(**overrides), content_type='application/json'
        )

    @override_settings(TURNSTILE_SECRET_KEY='')
    def test_sin_secret_el_checkout_funciona_igual_que_antes(self):
        self.assertEqual(self.enviar().status_code, 201)

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_crear_sin_token_se_rechaza(self):
        response = self.enviar()
        self.assertEqual(response.status_code, 403)
        self.assertIn('captcha', response.json())

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_crear_con_token_valido_se_acepta(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta(True)):
            response = self.enviar(captcha_token='token-bueno')
        self.assertEqual(response.status_code, 201)

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_crear_con_token_invalido_se_rechaza(self):
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta(False)):
            response = self.enviar(captcha_token='token-malo')
        self.assertEqual(response.status_code, 403)

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_corregir_una_reserva_ya_creada_no_vuelve_a_pedir_token(self):
        """El token de Turnstile es de un solo uso.

        El checkout reenvia la misma reserva cada vez que el cliente corrige la
        fecha o reintenta tras un error, y esos envios son un upsert sobre la
        misma fila. Exigir token en cada uno romperia el checkout al segundo
        cambio. Cobrarlo solo al crear deja el costo donde importa: un bot paga
        un captcha por cada reserva nueva que quiera meter.
        """
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta(True)):
            self.assertEqual(self.enviar(captcha_token='token-bueno').status_code, 201)

        with mock.patch('apps.bookings.captcha.requests.post') as post:
            response = self.enviar(numero_personas=3)
        self.assertEqual(response.status_code, 200)
        post.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=SECRET)
    def test_el_token_no_se_guarda_en_la_reserva(self):
        """No es un dato del negocio y no debe terminar en la base."""
        with mock.patch('apps.bookings.captcha.requests.post', return_value=_respuesta(True)):
            response = self.enviar(captcha_token='token-bueno')
        self.assertNotIn('captcha_token', response.json())
