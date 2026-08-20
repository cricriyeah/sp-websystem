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
        response = requests.post(
            URL_VERIFICACION,
            data={
                'secret': settings.TURNSTILE_SECRET_KEY,
                'response': token,
                # Le da a Cloudflare la IP real del cliente para su propio
                # analisis. Es la misma que usa la constancia del deslinde.
                'remoteip': ip,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.error(
            'No se pudo verificar el captcha contra Cloudflare, se deja pasar la reserva',
            exc_info=True,
        )
        return True

    return bool(response.json().get('success'))
