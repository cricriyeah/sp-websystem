"""La compra avisada a Meta desde el servidor (apps/payments/meta_capi.py)."""
import hashlib
from datetime import UTC, datetime
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.payments import meta_capi

LLAVES = {'META_PIXEL_ID': '123', 'META_CAPI_TOKEN': 'tok', 'FRONTEND_URL': 'https://sitio.test'}
CON_CONSENTIMIENTO = {'fbp': 'fb.1.111.222', 'fbc': 'fb.1.111.abc', 'landing': '/es/sede/la-paz'}


def _datos(**cambios):
    datos = {
        'evento_id': 'reserva-7', 'valor': '13096.40', 'moneda': 'mxn',
        'correo': ' Ana@Correo.com ', 'telefono': '+52 612 123 4567',
        'atribucion': CON_CONSENTIMIENTO, 'momento': datetime(2026, 11, 11, 18, 0, tzinfo=UTC),
    }
    datos.update(cambios)
    return datos


@override_settings(**LLAVES, META_CAPI_SIN_CONSENTIMIENTO=False, META_CAPI_TEST_CODE='')
class EventoCompraTests(SimpleTestCase):
    def test_arma_el_purchase_con_el_mismo_id_que_el_pixel(self):
        evento = meta_capi.evento_compra(**_datos())
        self.assertEqual(evento['event_name'], 'Purchase')
        self.assertEqual(evento['event_id'], 'reserva-7')
        self.assertEqual(evento['action_source'], 'website')
        self.assertEqual(evento['custom_data'], {'value': 13096.4, 'currency': 'MXN'})
        self.assertEqual(evento['event_source_url'], 'https://sitio.test/es/sede/la-paz')
        self.assertEqual(evento['event_time'], int(datetime(2026, 11, 11, 18, 0, tzinfo=UTC).timestamp()))

    def test_correo_y_telefono_van_cifrados_y_normalizados(self):
        usuario = meta_capi.evento_compra(**_datos())['user_data']
        self.assertEqual(usuario['em'], [hashlib.sha256(b'ana@correo.com').hexdigest()])
        self.assertEqual(usuario['ph'], [hashlib.sha256(b'526121234567').hexdigest()])
        self.assertEqual(usuario['fbp'], 'fb.1.111.222')
        self.assertEqual(usuario['fbc'], 'fb.1.111.abc')
        self.assertNotIn('Ana', str(usuario))

    def test_sin_la_cookie_del_pixel_no_se_manda(self):
        self.assertIsNone(meta_capi.evento_compra(**_datos(atribucion={'utm_source': 'facebook'})))
        self.assertIsNone(meta_capi.evento_compra(**_datos(atribucion=None)))

    @override_settings(META_CAPI_SIN_CONSENTIMIENTO=True)
    def test_el_dueno_puede_mandar_tambien_sin_consentimiento(self):
        evento = meta_capi.evento_compra(**_datos(atribucion={}))
        self.assertNotIn('fbp', evento['user_data'])
        self.assertIn('em', evento['user_data'])

    def test_sin_valor_no_hay_compra(self):
        self.assertIsNone(meta_capi.evento_compra(**_datos(valor=None)))
        self.assertIsNone(meta_capi.evento_compra(**_datos(valor='0')))


@override_settings(**LLAVES, META_CAPI_SIN_CONSENTIMIENTO=False, META_CAPI_TEST_CODE='')
class EnviarCompraTests(SimpleTestCase):
    @mock.patch('apps.payments.meta_capi.requests.post')
    def test_manda_al_pixel_con_el_token(self, post):
        post.return_value = mock.Mock(status_code=200)
        self.assertTrue(meta_capi.enviar_compra(**_datos()))
        url = post.call_args.args[0]
        cuerpo = post.call_args.kwargs['json']
        self.assertEqual(url, f'https://graph.facebook.com/{meta_capi.VERSION_API}/123/events')
        self.assertEqual(cuerpo['access_token'], 'tok')
        self.assertEqual(cuerpo['data'][0]['event_id'], 'reserva-7')
        self.assertNotIn('test_event_code', cuerpo)

    @override_settings(META_CAPI_TEST_CODE='TEST1')
    @mock.patch('apps.payments.meta_capi.requests.post')
    def test_con_codigo_de_prueba_lo_agrega(self, post):
        post.return_value = mock.Mock(status_code=200)
        meta_capi.enviar_compra(**_datos())
        self.assertEqual(post.call_args.kwargs['json']['test_event_code'], 'TEST1')

    @override_settings(META_CAPI_TOKEN='')
    @mock.patch('apps.payments.meta_capi.requests.post')
    def test_sin_token_no_hace_nada(self, post):
        self.assertFalse(meta_capi.enviar_compra(**_datos()))
        post.assert_not_called()

    @mock.patch('apps.payments.meta_capi.requests.post', side_effect=OSError('sin red'))
    def test_un_fallo_de_red_nunca_lanza(self, _post):
        with self.assertLogs('apps.payments.meta_capi', level='ERROR'):
            self.assertFalse(meta_capi.enviar_compra(**_datos()))

    @mock.patch('apps.payments.meta_capi.requests.post')
    def test_un_rechazo_de_meta_queda_en_el_log(self, post):
        post.return_value = mock.Mock(status_code=400, text='bad')
        with self.assertLogs('apps.payments.meta_capi', level='WARNING'):
            self.assertFalse(meta_capi.enviar_compra(**_datos()))
