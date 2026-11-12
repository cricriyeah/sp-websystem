"""La compra, avisada a Meta desde el servidor (API de Conversiones; plan de marketing, punto 6).

El navegador ya manda `Purchase` con el pixel (`frontend/src/lib/medicion.ts`) cuando el cliente aceptó las cookies.
Un bloqueador de anuncios o el navegador de iOS lo pueden tirar; el servidor no. Los dos mandan el mismo `event_id`
(`reserva-<folio>` u `orden-<folio>`) y Meta se queda con uno.

Consentimiento: por defecto solo se manda cuando el cliente aceptó las cookies de medición, y eso se sabe porque
la reserva trae la cookie `_fbp` del pixel en `Reserva.atribucion` (el navegador solo la crea tras aceptar).
`META_CAPI_SIN_CONSENTIMIENTO=1` manda también las demás; es decisión del dueño y pide cambiar el aviso de
privacidad antes (el correo y el teléfono viajan a Meta, cifrados con SHA-256).

Sin `META_PIXEL_ID` o `META_CAPI_TOKEN` no hace nada. Nunca lanza: medir no puede romper un cobro.
"""
import hashlib
import logging
import re
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERSION_API = 'v21.0'
TIEMPO_MAXIMO = 5  # segundos


def _cifrar(valor):
    return hashlib.sha256(valor.strip().lower().encode('utf-8')).hexdigest()


def _digitos(telefono):
    return re.sub(r'\D', '', telefono or '')


def configurada():
    return bool(getattr(settings, 'META_PIXEL_ID', '') and getattr(settings, 'META_CAPI_TOKEN', ''))


def evento_compra(*, evento_id, valor, moneda, correo, telefono, atribucion, momento=None):
    """El evento `Purchase` como lo pide Meta, o `None` si no se debe mandar (sin consentimiento o sin valor)."""
    atribucion = atribucion or {}
    con_consentimiento = bool(atribucion.get('fbp'))
    if not con_consentimiento and not getattr(settings, 'META_CAPI_SIN_CONSENTIMIENTO', False):
        return None
    try:
        monto = round(float(valor), 2)
    except (TypeError, ValueError):
        return None
    if monto <= 0:
        return None

    datos_usuario = {}
    if correo:
        datos_usuario['em'] = [_cifrar(correo)]
    if _digitos(telefono):
        datos_usuario['ph'] = [_cifrar(_digitos(telefono))]
    for clave in ('fbp', 'fbc'):
        if atribucion.get(clave):
            datos_usuario[clave] = atribucion[clave]

    evento = {
        'event_name': 'Purchase',
        'event_time': int(momento.timestamp() if momento else time.time()),
        'event_id': evento_id,
        'action_source': 'website',
        'user_data': datos_usuario,
        'custom_data': {'value': monto, 'currency': (moneda or 'MXN').upper()},
    }
    sitio = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
    if sitio:
        evento['event_source_url'] = sitio + (atribucion.get('landing') or '/')
    return evento


def enviar_compra(**datos):
    """Manda la compra a Meta. Devuelve `True` si Meta la recibió. Nunca lanza."""
    try:
        if not configurada():
            return False
        evento = evento_compra(**datos)
        if evento is None:
            return False
        cuerpo = {'data': [evento], 'access_token': settings.META_CAPI_TOKEN}
        codigo_prueba = getattr(settings, 'META_CAPI_TEST_CODE', '')
        if codigo_prueba:
            cuerpo['test_event_code'] = codigo_prueba
        respuesta = requests.post(
            f'https://graph.facebook.com/{VERSION_API}/{settings.META_PIXEL_ID}/events',
            json=cuerpo,
            timeout=TIEMPO_MAXIMO,
        )
        if respuesta.status_code >= 400:
            logger.warning('Meta rechazó la compra %s: %s %s', evento['event_id'], respuesta.status_code, respuesta.text[:300])
            return False
        return True
    except Exception:  # noqa: BLE001 — medir nunca rompe un cobro
        logger.exception('No se pudo avisar la compra a Meta')
        return False
