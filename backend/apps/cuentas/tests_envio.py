"""Envio del correo fuera de la peticion (`envio.despachar`).

Responder despues de hablar con Resend (~300 ms) solo cuando la cuenta existe seria un oraculo de
existencia por tiempo; por eso el envio sale en un hilo aparte (y sincrono solo al correr pruebas).
"""
import logging
import threading
from unittest import mock

from django.test import SimpleTestCase

from . import envio

MODO_PRODUCCION = mock.patch('apps.cuentas.envio.sys.argv', ['manage.py', 'runserver'])


class DespacharEnPruebasTests(SimpleTestCase):
    def test_bajo_manage_py_test_corre_sincrono_en_el_mismo_hilo(self):
        hilos = []
        resultado = envio.despachar(lambda *a: hilos.append((threading.current_thread(), a)), 'x', 7)
        self.assertIsNone(resultado)
        self.assertEqual(hilos, [(threading.current_thread(), ('x', 7))])

    def test_en_modo_sincrono_no_toca_las_conexiones(self):
        with mock.patch('apps.cuentas.envio.connections') as conexiones:
            envio.despachar(lambda: None)
        conexiones.close_all.assert_not_called()


class DespacharEnSegundoPlanoTests(SimpleTestCase):
    def test_corre_en_otro_hilo_daemon(self):
        capturado = {}

        def tarea(*args):
            capturado['hilo'] = threading.current_thread()
            capturado['args'] = args

        with MODO_PRODUCCION, mock.patch('apps.cuentas.envio.connections'):
            hilo = envio.despachar(tarea, 'a', 'b')
            hilo.join(timeout=5)

        self.assertIsNot(capturado['hilo'], threading.current_thread())
        self.assertTrue(capturado['hilo'].daemon)
        self.assertEqual(capturado['args'], ('a', 'b'))

    def test_regresa_antes_de_que_termine_el_envio(self):
        """Lo que hace la respuesta indistinguible: no espera a Resend."""
        liberar = threading.Event()
        terminado = threading.Event()

        def tarea():
            liberar.wait(timeout=5)
            terminado.set()

        with MODO_PRODUCCION, mock.patch('apps.cuentas.envio.connections'):
            hilo = envio.despachar(tarea)
            self.assertFalse(terminado.is_set())
            liberar.set()
            hilo.join(timeout=5)
        self.assertTrue(terminado.is_set())

    def test_cierra_la_conexion_del_hilo_al_terminar_aunque_falle(self):
        with MODO_PRODUCCION, mock.patch('apps.cuentas.envio.connections') as conexiones:
            with self.assertLogs('apps.cuentas.envio', level=logging.ERROR):
                hilo = envio.despachar(lambda: 1 / 0)
                hilo.join(timeout=5)
        conexiones.close_all.assert_called_once()


class FalloDelEnvioTests(SimpleTestCase):
    def test_un_fallo_no_se_propaga_y_solo_registra_la_clase_del_error(self):
        secreto = 'texto-que-no-debe-aparecer-en-el-log'

        def tarea():
            raise RuntimeError(secreto)

        with self.assertLogs('apps.cuentas.envio', level=logging.ERROR) as logs:
            envio.despachar(tarea)  # sincrono: si propagara, esta linea fallaria

        salida = '\n'.join(logs.output)
        self.assertIn('RuntimeError', salida)
        # Ni el mensaje de la excepcion (podria traer el codigo) ni una traza con las variables locales.
        self.assertNotIn(secreto, salida)
        self.assertNotIn('Traceback', salida)

    def test_un_fallo_en_el_hilo_tampoco_se_propaga(self):
        with MODO_PRODUCCION, mock.patch('apps.cuentas.envio.connections'):
            with self.assertLogs('apps.cuentas.envio', level=logging.ERROR) as logs:
                hilo = envio.despachar(lambda: 1 / 0)
                hilo.join(timeout=5)
        self.assertIn('ZeroDivisionError', '\n'.join(logs.output))
