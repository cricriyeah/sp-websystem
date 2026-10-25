"""El limite de peticiones no se evade escribiendo `X-Forwarded-For`.

DRF sin `NUM_PROXIES` cuenta por el valor completo de la cabecera, que escribe el cliente. Con un salto
de confianza (Render) usa la entrada que agrego el proxy, la unica que el cliente no puede inventar.
"""
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import ScopedRateThrottle

REST = {'NUM_PROXIES': 1}


class IdentidadDelLimiteTests(SimpleTestCase):
    def ident(self, **meta):
        request = APIRequestFactory().get('/', **meta)
        return ScopedRateThrottle().get_ident(request)

    @override_settings(REST_FRAMEWORK=REST)
    def test_con_un_salto_de_confianza_usa_la_entrada_que_agrego_el_proxy(self):
        # El cliente escribe «9.9.9.9»; el proxy agrega la IP real al final.
        self.assertEqual(self.ident(HTTP_X_FORWARDED_FOR='9.9.9.9, 203.0.113.7'), '203.0.113.7')

    @override_settings(REST_FRAMEWORK=REST)
    def test_cambiar_la_cabecera_no_cambia_la_identidad(self):
        a = self.ident(HTTP_X_FORWARDED_FOR='1.1.1.1, 203.0.113.7')
        b = self.ident(HTTP_X_FORWARDED_FOR='2.2.2.2, 203.0.113.7')
        self.assertEqual(a, b)

    @override_settings(REST_FRAMEWORK={'NUM_PROXIES': None})
    def test_sin_num_proxies_la_cabecera_completa_define_la_identidad_el_fallo_que_se_corrige(self):
        a = self.ident(HTTP_X_FORWARDED_FOR='1.1.1.1, 203.0.113.7')
        b = self.ident(HTTP_X_FORWARDED_FOR='2.2.2.2, 203.0.113.7')
        self.assertNotEqual(a, b)
