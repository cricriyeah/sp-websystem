"""Campo de texto secreto: cifrado en la base, texto normal en Python.

Las llaves de Stripe de cada Empresa vivian en texto plano en `tenancy_empresa`: quien pudiera leer la
base (un respaldo filtrado, el panel de Supabase, una cuenta comprometida) se llevaba llaves capaces de
devolver dinero y leer datos de clientes. Este campo las guarda cifradas (Fernet, AES-128-CBC con
firma) con una clave que NO vive en la base sino en una variable de entorno de Render.

Reglas que no hay que romper:

- El valor en Python siempre es el texto real: el admin, `stripe_client`, el webhook y los chequeos
  no saben que hay cifrado.
- Sin `STRIPE_KEYS_ENCRYPTION_KEY` se guarda en texto plano, como antes: poner la variable es lo que
  enciende el cifrado, y un despliegue sin ella no se cae. Los valores en texto plano que ya existan
  se leen igual y se cifran la proxima vez que se guarden (o con `manage.py cifrar_llaves_stripe`).
- La variable admite varias claves separadas por coma: la PRIMERA cifra, todas descifran. Rotar la
  clave es anteponer la nueva, correr `cifrar_llaves_stripe` y retirar la vieja.
- Si un valor cifrado no se puede descifrar (clave perdida o equivocada) NO se inventa un valor vacio:
  se devuelve el texto cifrado tal cual y se registra el error. Asi Stripe rechaza la llave (el cobro
  falla limpio) y un guardado del admin no borra el dato, porque lo cifrado no se vuelve a cifrar.
- Un filtro `filter(stripe_secret_key=...)` no sirve (cada cifrado es distinto). Nadie lo usa.
"""
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

PREFIJO = 'enc:v1:'


def claves_de_cifrado():
    """Las claves configuradas, la primera es la que cifra. Lista vacia = cifrado apagado."""
    crudo = getattr(settings, 'STRIPE_KEYS_ENCRYPTION_KEY', '') or ''
    return [parte.strip() for parte in crudo.split(',') if parte.strip()]


def _fernet():
    claves = claves_de_cifrado()
    return MultiFernet([Fernet(clave) for clave in claves]) if claves else None


def clave_valida(clave):
    """True si `clave` es una clave Fernet (32 bytes en base64 seguro para URL)."""
    try:
        Fernet(clave)
    except (ValueError, TypeError):
        return False
    return True


def cifrar(texto):
    """El texto cifrado con prefijo, o el mismo texto si no hay clave o ya viene cifrado."""
    if not texto or texto.startswith(PREFIJO):
        return texto
    fernet = _fernet()
    if fernet is None:
        return texto
    return PREFIJO + fernet.encrypt(texto.encode()).decode()


def descifrar(valor):
    """El texto real, o `valor` sin cambios si es texto plano o no se puede descifrar."""
    if not valor or not valor.startswith(PREFIJO):
        return valor
    fernet = _fernet()
    if fernet is None:
        logger.error('Hay un valor cifrado en la base y STRIPE_KEYS_ENCRYPTION_KEY no esta definida.')
        return valor
    try:
        return fernet.decrypt(valor[len(PREFIJO):].encode()).decode()
    except InvalidToken:
        logger.error('No se pudo descifrar un valor guardado: la clave de cifrado no es la que lo cifro.')
        return valor


class CampoSecreto(models.CharField):
    description = 'Texto secreto cifrado en la base'

    def __init__(self, *args, **kwargs):
        # Un Fernet de 110 caracteres de llave mide unos 230: 200 se quedaba corto.
        kwargs.setdefault('max_length', 600)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        return descifrar(value)

    def get_prep_value(self, value):
        return cifrar(super().get_prep_value(value))
