"""Utilidades compartidas por los tests de las apps."""

from django.core.cache import cache
from django.test import TestCase


class ApiTestCase(TestCase):
    """Base para los tests que pegan a la API publica.

    DRF lleva la cuenta de peticiones por IP en el cache de Django, y ese cache
    **no** se reinicia entre tests como si pasa con la base de datos. Sin esto
    una clase hereda el contador de la anterior y revienta con 429 por peticiones
    que no hizo: un fallo que no tiene nada que ver con lo que se estaba probando
    y que ademas aparece y desaparece segun el orden en que corran los tests.

    Se limpia en `_pre_setup` — el gancho que corre siempre, antes de `setUp` —
    a proposito: casi todas las clases definen su propio `setUp` sin llamar a
    `super()`, asi que un `setUp` heredado nunca correria.

    El throttle queda **activo** durante los tests, no desactivado: es la misma
    configuracion que produccion, y asi un 429 inesperado se descubre aqui y no
    en el checkout de un cliente.
    """

    def _pre_setup(self):
        super()._pre_setup()
        cache.clear()
