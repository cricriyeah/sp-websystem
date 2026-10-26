"""Verificacion de Cloudflare Turnstile para el checkout publico.

`POST /api/reservas/` es la unica puerta por la que entra una reserva y no pide
autenticacion: sin esto, lo unico que la separa de un bot es el throttle de
20/min por IP, que se esquiva rotando direcciones.

Se eligio Turnstile sobre reCAPTCHA porque es gratis sin tope, no le pone un
rompecabezas al cliente en el caso normal, y no mete una dependencia de Google en
el checkout.

Como Stripe y Resend, se enciende sola cuando su variable de entorno existe: sin
`TURNSTILE_SECRET_KEY` la verificacion es un no-op y el checkout se comporta
igual que antes. Asi local y CI no necesitan llaves.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

URL_VERIFICACION = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TIMEOUT_SEGUNDOS = 10
# La recuperacion de contrasena espera menos: una persona esta mirando la pantalla y, si Cloudflare tarda,
# se le dice que reintente en vez de dejarla colgada.
TIMEOUT_OBLIGATORIO_SEGUNDOS = 5
# Cloudflare documenta tokens de hasta 2048 caracteres; uno mas largo ni se consulta.
MAX_LARGO_TOKEN = 2048


def _consultar_siteverify(token, ip, timeout):
    """La llamada a Cloudflare, compartida por la variante abierta y la obligatoria."""
    return requests.post(
        URL_VERIFICACION,
        data={
            'secret': settings.TURNSTILE_SECRET_KEY,
            'response': token,
            # Le da a Cloudflare la IP real del cliente para su propio
            # analisis. Es la misma que usa la constancia del deslinde.
            'remoteip': ip,
        },
        timeout=timeout,
    )


def verificar_turnstile(token, ip):
    """True si el token es bueno (o si el gate esta apagado).

    **Falla abierta a proposito.** Si Cloudflare no responde se deja pasar y se
    registra el error. Lo que un bot consigue cruzando este gate son filas basura
    en el panel, no dinero: `crear-pago` reusa el PaymentIntent y exige el
    `checkout_id`, asi que por ahi no se generan cobros en masa. Fallar cerrado
    convertiria una caida de Cloudflare en un checkout muerto, y eso si cuesta
    reservas reales.
    """
    if not settings.TURNSTILE_SECRET_KEY:
        return True

    # Sin token no hay nada que preguntar: la llamada gastaria una peticion para
    # recibir el mismo `success: false` que ya sabemos.
    if not token:
        return False

    try:
        response = _consultar_siteverify(token, ip, TIMEOUT_SEGUNDOS)
        response.raise_for_status()
    except requests.RequestException:
        logger.error(
            'No se pudo verificar el captcha contra Cloudflare, se deja pasar la reserva',
            exc_info=True,
        )
        return True

    return bool(response.json().get('success'))


def verificar_turnstile_obligatorio(token, ip, *, accion, hostname):
    """True solo si Cloudflare confirma el token Y fue emitido para esta accion y este sitio.

    **Falla cerrada.** Es el opuesto de `verificar_turnstile`: la recuperacion de contrasena es la
    puerta a cualquier cuenta, asi que sin secreto, sin token, con Cloudflare caido, con una
    respuesta rara o con un token de otra accion u otro hostname, se rechaza. Una caida de
    Cloudflare deja a nadie recuperando su contrasena un rato; dejarla abierta lo dejaria sin freno
    contra la fuerza bruta del codigo. `action` y `hostname` impiden reusar un token del checkout
    publico (misma llave, otra accion) contra este formulario.

    Nunca escribe el token en el log.
    """
    if not settings.TURNSTILE_SECRET_KEY or not accion or not hostname:
        return False

    if not token or not isinstance(token, str) or len(token) > MAX_LARGO_TOKEN:
        return False

    try:
        response = _consultar_siteverify(token, ip, TIMEOUT_OBLIGATORIO_SEGUNDOS)
    except requests.RequestException as exc:
        logger.error('No se pudo verificar el captcha obligatorio contra Cloudflare (%s)', type(exc).__name__)
        return False

    if response.status_code != 200:
        logger.error('Cloudflare respondio %s al verificar el captcha obligatorio', response.status_code)
        return False

    try:
        datos = response.json()
    except ValueError:
        logger.error('Cloudflare devolvio una respuesta que no es JSON al verificar el captcha obligatorio')
        return False

    if not isinstance(datos, dict) or datos.get('success') is not True:
        return False

    return (
        isinstance(datos.get('action'), str)
        and isinstance(datos.get('hostname'), str)
        and datos['action'] == accion
        and datos['hostname'].lower() == hostname.lower()
    )
