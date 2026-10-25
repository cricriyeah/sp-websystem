"""El limite de peticiones no se evade escribiendo `X-Forwarded-For` ni agrupa a todos tras Cloudflare."""
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.bookings.ip_cliente import LimitePorIpDelCliente, ip_del_cliente


def peticion(**meta):
    return APIRequestFactory().get('/', **meta)


@override_settings(TRUSTED_PROXY_COUNT=1)
class IdentidadDelLimiteTests(SimpleTestCase):
    def ident(self, **meta):
        return LimitePorIpDelCliente().get_ident(peticion(**meta))

    def test_el_limite_usa_la_ip_real_del_cliente(self):
        self.assertEqual(self.ident(HTTP_X_FORWARDED_FOR='9.9.9.9, 203.0.113.7'), '203.0.113.7')

    def test_cambiar_la_cabecera_no_cambia_la_identidad(self):
        a = self.ident(HTTP_X_FORWARDED_FOR='1.1.1.1, 203.0.113.7')
        b = self.ident(HTTP_X_FORWARDED_FOR='2.2.2.2, 203.0.113.7')
        self.assertEqual(a, b)

    def test_detras_de_cloudflare_no_se_agrupa_a_todos_en_la_ip_del_nodo(self):
        # Cliente 177.x -> Cloudflare 172.64.x -> Render: la lista termina en el nodo de Cloudflare.
        uno = self.ident(HTTP_X_FORWARDED_FOR='177.10.20.30, 172.64.1.5')
        otro = self.ident(HTTP_X_FORWARDED_FOR='177.99.88.77, 172.64.1.5')
        self.assertEqual(uno, '177.10.20.30')
        self.assertNotEqual(uno, otro)


@override_settings(TRUSTED_PROXY_COUNT=1)
class IpDelClienteTests(SimpleTestCase):
    def ip(self, forwarded='', remota='198.51.100.7'):
        meta = {'REMOTE_ADDR': remota}
        if forwarded:
            meta['HTTP_X_FORWARDED_FOR'] = forwarded
        return ip_del_cliente(peticion(**meta))

    def test_un_nodo_de_cloudflare_al_final_se_salta(self):
        self.assertEqual(self.ip('177.10.20.30, 172.64.1.5'), '177.10.20.30')

    def test_cloudflare_y_el_balanceador_interno_se_saltan(self):
        self.assertEqual(self.ip('177.10.20.30, 162.158.9.9, 10.0.3.4'), '177.10.20.30')

    def test_lo_que_el_cliente_escribe_a_la_izquierda_no_cuenta(self):
        self.assertEqual(self.ip('1.2.3.4, 177.10.20.30, 172.64.1.5'), '177.10.20.30')

    def test_una_ip_de_cloudflare_escrita_por_el_cliente_no_engana(self):
        self.assertEqual(self.ip('172.64.0.1, 177.10.20.30'), '177.10.20.30')

    def test_ipv6_de_cloudflare_tambien_se_salta(self):
        self.assertEqual(self.ip('2806:1:2::3, 2606:4700:10::6814:1'), '2806:1:2::3')

    def test_sin_header_se_usa_la_ip_de_la_conexion(self):
        self.assertEqual(self.ip(''), '198.51.100.7')

    def test_si_todo_el_header_son_proxies_se_usa_la_ip_de_la_conexion(self):
        self.assertEqual(self.ip('172.64.1.5, 10.0.0.1'), '198.51.100.7')

    def test_algo_que_no_es_una_ip_no_se_adivina_se_usa_la_conexion(self):
        self.assertEqual(self.ip('no-es-ip, 172.64.1.5'), '198.51.100.7')
        self.assertEqual(self.ip('basura'), '198.51.100.7')

    def test_una_ip_de_cloudflare_escrita_como_ipv6_mapeada_tambien_se_salta(self):
        self.assertEqual(self.ip('177.10.20.30, ::ffff:172.64.1.5'), '177.10.20.30')

    def test_una_ip_del_cliente_ipv4_mapeada_se_devuelve_como_ipv4(self):
        self.assertEqual(self.ip('::ffff:177.10.20.30, 172.64.1.5'), '177.10.20.30')

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_sin_proxy_de_confianza_no_se_le_cree_al_header(self):
        self.assertEqual(self.ip('1.2.3.4'), '198.51.100.7')
