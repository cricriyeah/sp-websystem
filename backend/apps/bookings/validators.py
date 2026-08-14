"""Validadores de los datos de contacto del cliente.

El criterio no es el mismo para los dos campos, y la diferencia es deliberada:

- El **telefono** se aprieta. Es con lo que la vendedora contacta al cliente y
  por donde sale la confirmacion de WhatsApp. Un telefono invalido significa
  alguien parado en el muelle a las 6 de la mañana sin que nadie lo espere.
- El **nombre** se aprieta poco. La regla intuitiva ("solo letras") rompe
  personas reales: acentos, apostrofos (O'Brien), guiones (Garcia-Lopez). Dejar
  a alguien sin poder reservar es peor que guardar un nombre raro — un nombre
  raro la vendedora lo ve y lo corrige por telefono.
"""
import re

from django.core.exceptions import ValidationError

# Rango que cubre un numero nacional mexicano (10) y cualquier internacional con
# lada, hasta el maximo que define el estandar E.164 (15).
DIGITOS_MIN = 10
DIGITOS_MAX = 15

# Lo que la gente escribe de verdad al teclear un telefono.
SEPARADORES_TELEFONO = re.compile(r'^[\d\s+()\-.]+$')


def validar_telefono(value):
    """Acepta como lo escribe la gente, exige que tenga numero suficiente.

    `612 123 4567`, `+52 1 612 123 4567` y `(612) 123-4567` pasan. `asdf` y
    `123` no. No se normaliza aqui a proposito: se guarda lo que el cliente
    escribio, y el formateo para marcar vive en `telefono_marcable()`
    (apps/bookings/admin.py), que ya sabe completar la lada.
    """
    texto = (value or '').strip()

    if not SEPARADORES_TELEFONO.match(texto):
        raise ValidationError(
            'El telefono solo puede llevar numeros y los signos + ( ) - . '
            'Escribelo con lada, por ejemplo 612 123 4567.'
        )

    digitos = len(re.sub(r'\D', '', texto))
    if digitos < DIGITOS_MIN:
        raise ValidationError(
            f'El telefono esta incompleto: tiene {digitos} digitos y hacen falta '
            f'al menos {DIGITOS_MIN} (con lada).'
        )
    if digitos > DIGITOS_MAX:
        raise ValidationError(f'El telefono tiene mas de {DIGITOS_MAX} digitos.')


def validar_nombre_persona(value):
    """Al menos una letra y ningun digito. Nada mas.

    Deliberadamente permisivo con acentos, apostrofos, guiones y espacios: son
    parte de nombres reales. Lo unico que se rechaza es lo que claramente no es
    un nombre — `12345`, `----`, o un campo con numeros dentro.
    """
    texto = (value or '').strip()

    if any(c.isdigit() for c in texto):
        raise ValidationError('El nombre no puede llevar numeros.')

    if not any(c.isalpha() for c in texto):
        raise ValidationError('Escribe tu nombre.')
