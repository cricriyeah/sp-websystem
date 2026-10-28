"""Telefono del cliente en el formato que piden `wa.me`, `tel:` y la API de WhatsApp.

Sin imports de modelos a proposito: lo usan el validador, el admin y las notificaciones,
y un ciclo de imports aqui tumbaria los tres.
"""
import re

# Lada de Mexico, para completar los telefonos que el cliente escribio a 10 digitos.
LADA_PAIS = '52'

# Solo [0-9] ASCII: `\d` en Python tambien cuenta digitos arabes o devanagari, que ni
# `wa.me` ni Meta marcan.
_NO_DIGITO_ASCII = re.compile(r'[^0-9]')

# Con codigo de pais y `+` ya no hay que adivinar la lada, y existen paises con numeros
# totales de 7 a 9 digitos (Andorra +376, Groenlandia +299, Malvinas +500).
INTERNACIONAL_CORTO_MIN = 7
INTERNACIONAL_CORTO_MAX = 9


def digitos_ascii(texto):
    return _NO_DIGITO_ASCII.sub('', texto or '')


def es_internacional_corto(telefono):
    """`+` adelante y de 7 a 9 digitos en total, salvo prefijos 1 y 52.

    NANP (+1) y Mexico (+52) siempre suman 10 digitos o mas, asi que `+52 612 123`
    o `+1 212` son numeros incompletos y no se aceptan por esta via.
    """
    texto = (telefono or '').strip()
    if not texto.startswith('+') or not texto.isascii():
        return False
    digitos = digitos_ascii(texto)
    if not INTERNACIONAL_CORTO_MIN <= len(digitos) <= INTERNACIONAL_CORTO_MAX:
        return False
    return not digitos.startswith(('1', LADA_PAIS))


def telefono_marcable(telefono):
    """Telefono en digitos con lada de pais, como lo quieren `wa.me` y `tel:`.

    Con `+` el cliente ya dio su codigo de pais: se devuelven los digitos tal cual, sin
    anteponer 52. Sin `+`, los clientes escriben el numero como se les da la gana
    ('612 123 4567'): 10 digitos = numero nacional sin lada internacional (se antepone
    52). Un numero incompleto devuelve '' y la interfaz muestra el texto crudo en vez de
    un enlace roto.
    """
    texto = (telefono or '').strip()
    digitos = digitos_ascii(texto)
    if texto.startswith('+'):
        if len(digitos) >= 10 or es_internacional_corto(texto):
            return digitos
        return ''
    if len(digitos) == 10:
        return LADA_PAIS + digitos
    return digitos if len(digitos) >= 11 else ''
