"""Gate anti-bot del checkout (Cloudflare Turnstile).

La ruta que crea reservas es publica y sin autenticacion: el throttle de 20/min
por IP es lo unico que la separa de un bot que rote direcciones y llene el panel
de reservas basura. Ver apps/bookings/captcha.py.
"""
from datetime import date, timedelta
from unittest import mock

import requests
from django.test import override_settings

from apps.testing import ApiTestCase, crear_flota

from .captcha import verificar_turnstile

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


class CheckoutConCaptchaTests(ApiTestCase):
    """El gate montado sobre POST /api/reservas/."""

    CHECKOUT_ID = '22222222-2222-4222-8222-222222222222'

    def setUp(self):
        crear_flota()

    def payload(self, **overrides):
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
        }
        datos.update(overrides)
        return datos

    def enviar(self, **overrides):
        return self.client.post(
            '/api/reservas/', self.payload(**overrides), content_type='application/json'
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
