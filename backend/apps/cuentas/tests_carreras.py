"""Carreras al confirmar el codigo: dos peticiones simultaneas con el codigo bueno, o cien con uno malo.

Solo corren en Postgres: sqlite serializa toda escritura y `select_for_update` no hace nada ahi. La
prueba determinista del UPDATE condicional corre en los dos motores (ver `ConsumoCondicionalTests` en
tests_confirmar.py). Cada hilo abre su propia conexion, igual que dos navegadores.
"""
import threading
from datetime import timedelta
from unittest import mock

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.bookings.tests_concurrencia import SOLO_POSTGRES

from .models import CodigoRecuperacion
from .seguridad import hash_codigo
from .servicio import confirmar_codigo
from .testing import HASH_RAPIDO, PASSWORD_VIEJA, crear_usuario

CODIGO = '123456'
IP = '203.0.113.9'
ESPERA = 60


@SOLO_POSTGRES
@HASH_RAPIDO
class CarrerasAlConfirmarTests(TransactionTestCase):
    def setUp(self):
        parche = mock.patch('apps.cuentas.servicio.enviar_correo_contrasena_cambiada', return_value=True)
        parche.start()
        self.addCleanup(parche.stop)
        self.usuario = crear_usuario()
        CodigoRecuperacion.objects.create(
            usuario=self.usuario, codigo_hash=hash_codigo(self.usuario, CODIGO),
            vence_en=timezone.now() + timedelta(minutes=10),
        )

    def en_hilos(self, cantidad, tarea):
        """Corre `tarea(i)` en `cantidad` hilos que arrancan a la vez; devuelve (resultados, errores)."""
        barrera = threading.Barrier(cantidad)
        resultados, errores = [], []

        def trabajo(i):
            try:
                barrera.wait(timeout=ESPERA)
                resultados.append(tarea(i))
            except Exception as error:  # se reporta abajo; un hilo que revienta no debe callarse
                errores.append(error)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=trabajo, args=(i,)) for i in range(cantidad)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=ESPERA)
        return resultados, errores

    def test_dos_peticiones_con_el_codigo_correcto_solo_una_gana(self):
        contrasenas = ['Clave-Nueva-A-4q2#mar', 'Clave-Nueva-B-9z7%sol']
        resultados, errores = self.en_hilos(
            2, lambda i: confirmar_codigo(self.usuario.email, CODIGO, contrasenas[i], IP),
        )
        self.assertEqual(errores, [])
        self.assertEqual(sum(1 for r in resultados if r.exito), 1)
        self.usuario.refresh_from_db()
        # La contrasena que quedo es la de UNA de las dos, nunca la vieja ni una mezcla.
        self.assertTrue(any(self.usuario.check_password(c) for c in contrasenas))
        self.assertFalse(self.usuario.check_password(PASSWORD_VIEJA))
        self.assertIsNotNone(CodigoRecuperacion.objects.get(usuario=self.usuario).consumido_en)

    def test_veinte_peticiones_con_un_codigo_malo_nunca_pasan_de_cinco_intentos(self):
        resultados, errores = self.en_hilos(
            20, lambda i: confirmar_codigo(self.usuario.email, '000000', 'Clave-Nueva-4q2#mar', IP),
        )
        self.assertEqual(errores, [])
        self.assertFalse(any(r.exito for r in resultados))
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=self.usuario).intentos, 5)

    def test_con_el_codigo_agotado_ni_el_correcto_en_paralelo_cambia_la_contrasena(self):
        self.en_hilos(8, lambda i: confirmar_codigo(self.usuario.email, '000000', 'Clave-Nueva-4q2#mar', IP))
        resultados, errores = self.en_hilos(
            4, lambda i: confirmar_codigo(self.usuario.email, CODIGO, 'Clave-Nueva-4q2#mar', IP),
        )
        self.assertEqual(errores, [])
        self.assertFalse(any(r.exito for r in resultados))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(PASSWORD_VIEJA))
