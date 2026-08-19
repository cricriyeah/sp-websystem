"""Utilidades compartidas por los tests de las apps."""

from django.core.cache import cache
from django.test import TestCase

from apps.fleet.models import Embarcacion


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


# La flota real del negocio: 8 pangas de hasta 3 personas y 2 de hasta 5.
FLOTA_REAL = [(8, 3), (2, 5)]


def crear_flota(composicion=FLOTA_REAL):
    """Da de alta la flota en la base de pruebas. Idempotente.

    Hace falta en cualquier test que cree una reserva: desde que el cupo es
    consciente del tamano del grupo, sin pangas en la base no cabe nadie y la
    validacion rechaza todo. Es el mismo fallo seguro que en produccion — solo que
    ahi la flota se captura una vez y aqui hay que sembrarla.
    """
    if Embarcacion.objects.exists():
        return list(Embarcacion.objects.all())

    pangas = []
    for cuantas, capacidad in composicion:
        clase = Embarcacion.Clase.CHICA if capacidad <= 3 else Embarcacion.Clase.GRANDE
        for i in range(cuantas):
            pangas.append(Embarcacion(
                nombre=f'Panga {capacidad}-{i + 1}', clase=clase, capacidad_maxima=capacidad,
            ))
    return Embarcacion.objects.bulk_create(pangas)
