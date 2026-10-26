"""Primitivas criptograficas de la recuperacion de contrasena.

Aqui vive todo lo que toca el codigo en claro. El resto de la app lo maneja como `Secreto` o ya
hasheado, para que ningun `repr`, traza, log ni variable local capturada por Sentry lo imprima.
"""
import hmac
import json
import secrets

from django.conf import settings
from django.utils.crypto import salted_hmac

# Sal de cada uso: el mismo texto nunca produce el mismo HMAC en dos usos distintos.
_SAL_CODIGO = 'apps.cuentas.codigo'
_SAL_CORREO = 'apps.cuentas.correo'


class Secreto:
    """Envuelve un valor que no debe imprimirse jamas. `.revelar()` entrega el texto."""

    __slots__ = ('_valor',)

    def __init__(self, valor):
        self._valor = str(valor)

    def revelar(self):
        return self._valor

    def __repr__(self):
        return '<Secreto>'

    def __str__(self):
        return '<Secreto>'

    def __format__(self, especificacion):
        return format('<Secreto>', especificacion)


def _texto(codigo):
    return codigo.revelar() if isinstance(codigo, Secreto) else str(codigo)


def generar_codigo():
    """Seis digitos con ceros a la izquierda, del generador criptografico del sistema."""
    return Secreto(f'{secrets.randbelow(10**6):06d}')


def hash_codigo(usuario, codigo):
    """HMAC-SHA256 con `SECRET_KEY` atado al usuario Y al hash de su contrasena vigente.

    Un SHA-256 simple se rompe offline en milisegundos (10^6 combinaciones) si se filtra la base;
    con la llave del servidor no. Atarlo a `usuario.password` hace que el codigo muera si la contrasena
    cambia por otro camino. Se serializa como lista JSON para que ningun campo pueda «correrse» hacia
    el vecino y producir el mismo texto con otros valores.
    """
    mensaje = json.dumps([usuario.pk, usuario.password, _texto(codigo)])
    return salted_hmac(_SAL_CODIGO, mensaje, secret=settings.SECRET_KEY, algorithm='sha256').hexdigest()


def normalizar_correo(correo):
    return (correo or '').strip().lower()


def hash_correo(correo):
    """HMAC del correo normalizado (sin espacios ni mayusculas), para contar limites sin guardar direcciones."""
    return salted_hmac(
        _SAL_CORREO, normalizar_correo(correo), secret=settings.SECRET_KEY, algorithm='sha256'
    ).hexdigest()


def coincide(hash_guardado, hash_calculado):
    """Comparacion en tiempo constante de dos HMAC. Valores que no son texto ASCII no coinciden."""
    if not isinstance(hash_guardado, str) or not isinstance(hash_calculado, str):
        return False
    if not hash_guardado or not hash_calculado:
        return False
    try:
        return hmac.compare_digest(hash_guardado, hash_calculado)
    except TypeError:
        # compare_digest rechaza texto no ASCII; un hash valido nunca lo es.
        return False
