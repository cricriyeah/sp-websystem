"""Primitivas de la recuperacion de contrasena: generar, ocultar, hashear y comparar el codigo."""
import logging
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from . import seguridad
from .seguridad import Secreto, coincide, generar_codigo, hash_codigo, hash_correo

User = get_user_model()


def _usuario(pk=1, password='pbkdf2_sha256$100$sal$hash-uno'):
    """Usuario sin guardar: el hash solo lee `pk` y `password`."""
    return User(pk=pk, username=f'u{pk}', password=password)


class GenerarCodigoTests(SimpleTestCase):
    def test_rellena_con_ceros_a_seis_digitos(self):
        with mock.patch('apps.cuentas.seguridad.secrets.randbelow', return_value=7) as aleatorio:
            codigo = generar_codigo()
        self.assertEqual(codigo.revelar(), '000007')
        # Sale del generador criptografico, sobre el rango completo de seis digitos.
        aleatorio.assert_called_once_with(10**6)

    def test_siempre_son_seis_digitos(self):
        for _ in range(300):
            texto = generar_codigo().revelar()
            self.assertRegex(texto, r'^\d{6}$')

    def test_no_usa_el_modulo_random(self):
        self.assertFalse(hasattr(seguridad, 'random'))


class SecretoTests(SimpleTestCase):
    def test_repr_str_y_format_no_contienen_digitos(self):
        secreto = Secreto('483920')
        for texto in (repr(secreto), str(secreto), f'{secreto}', '%s' % secreto, '%r' % secreto, format(secreto, '>20')):
            self.assertNotIn('483920', texto)
            self.assertNotRegex(texto, r'\d')
            self.assertIn('Secreto', texto)

    def test_dentro_de_una_coleccion_tampoco_se_ve(self):
        secreto = Secreto('483920')
        self.assertNotIn('483920', repr([secreto]))
        self.assertNotIn('483920', repr({'codigo': secreto}))
        self.assertNotIn('483920', repr((secreto,)))

    def test_revelar_entrega_los_digitos(self):
        self.assertEqual(Secreto('483920').revelar(), '483920')

    def test_un_log_con_el_secreto_no_lo_imprime(self):
        with self.assertLogs('apps.cuentas.prueba', level='ERROR') as logs:
            logging.getLogger('apps.cuentas.prueba').error('codigo=%s y %r', Secreto('483920'), Secreto('483920'))
        self.assertNotIn('483920', '\n'.join(logs.output))


class HashCodigoTests(SimpleTestCase):
    def test_es_un_hmac_sha256_en_hexadecimal_que_no_contiene_el_codigo(self):
        resultado = hash_codigo(_usuario(), '483920')
        self.assertRegex(resultado, r'^[0-9a-f]{64}$')
        self.assertNotIn('483920', resultado)

    def test_es_determinista_y_acepta_secreto_o_texto(self):
        usuario = _usuario()
        self.assertEqual(hash_codigo(usuario, '483920'), hash_codigo(usuario, '483920'))
        self.assertEqual(hash_codigo(usuario, '483920'), hash_codigo(usuario, Secreto('483920')))

    def test_cambia_por_usuario(self):
        self.assertNotEqual(hash_codigo(_usuario(pk=1), '483920'), hash_codigo(_usuario(pk=2), '483920'))

    def test_cambia_por_codigo(self):
        usuario = _usuario()
        self.assertNotEqual(hash_codigo(usuario, '483920'), hash_codigo(usuario, '483921'))

    def test_cambia_cuando_cambia_la_contrasena_del_usuario(self):
        """Un codigo pedido antes de cambiar la contrasena por otro camino deja de servir."""
        antes = hash_codigo(_usuario(password='pbkdf2_sha256$100$sal$hash-uno'), '483920')
        despues = hash_codigo(_usuario(password='pbkdf2_sha256$100$sal$hash-dos'), '483920')
        self.assertNotEqual(antes, despues)

    def test_depende_de_la_llave_secreta_del_proyecto(self):
        usuario = _usuario()
        normal = hash_codigo(usuario, '483920')
        with self.settings(SECRET_KEY='otra-llave-distinta-' * 3):
            self.assertNotEqual(normal, hash_codigo(usuario, '483920'))

    def test_los_separadores_no_permiten_colisiones_entre_campos(self):
        """`1:2:3` no puede salir de dos combinaciones distintas de usuario, contrasena y codigo."""
        a = hash_codigo(_usuario(pk=1, password='a:b'), '123456')
        b = hash_codigo(_usuario(pk=1, password='a'), 'b:123456')
        self.assertNotEqual(a, b)


class CoincideTests(SimpleTestCase):
    def test_usa_compare_digest(self):
        with mock.patch('apps.cuentas.seguridad.hmac.compare_digest', return_value=True) as comparar:
            self.assertTrue(coincide('a' * 64, 'a' * 64))
        comparar.assert_called_once_with('a' * 64, 'a' * 64)

    def test_igual_y_distinto(self):
        self.assertTrue(coincide('a' * 64, 'a' * 64))
        self.assertFalse(coincide('a' * 64, 'b' * 64))

    def test_valores_que_no_son_texto_no_coinciden_en_vez_de_lanzar(self):
        self.assertFalse(coincide(None, 'a' * 64))
        self.assertFalse(coincide('a' * 64, None))
        self.assertFalse(coincide('', 'a' * 64))
        self.assertFalse(coincide('á' * 64, 'a' * 64))


class HashCorreoTests(SimpleTestCase):
    def test_ignora_mayusculas_y_espacios(self):
        self.assertEqual(hash_correo('  Ana@Example.COM '), hash_correo('ana@example.com'))

    def test_correos_distintos_dan_hashes_distintos(self):
        self.assertNotEqual(hash_correo('ana@example.com'), hash_correo('ana@example.org'))

    def test_no_contiene_el_correo(self):
        resultado = hash_correo('ana@example.com')
        self.assertRegex(resultado, r'^[0-9a-f]{64}$')
        self.assertNotIn('ana', resultado)

    def test_no_se_confunde_con_el_hash_de_un_codigo(self):
        """Dominios de HMAC separados: el mismo texto no produce el mismo valor en los dos usos."""
        self.assertNotEqual(hash_correo('483920'), hash_codigo(_usuario(), '483920'))
