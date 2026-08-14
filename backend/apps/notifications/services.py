"""Confirmacion automatica al cliente cuando entra el pago.

Dos canales, ambos por HTTP y ambos opcionales: correo (Resend) y WhatsApp
(WhatsApp Business API de Meta). Cada uno se activa solo si sus variables de
entorno estan puestas — igual que Stripe, en local no hay llaves y no se manda
nada. Ninguna falla de notificacion debe tumbar el cobro: el webhook de Stripe
ya recibio el dinero, asi que todo error se registra y se sigue.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 10

PUNTO_DE_ENCUENTRO = 'Marina La Costa, Rangel y Navarro, La Paz, BCS'


def _asunto(reserva):
    return f'Reserva confirmada — {reserva.fecha} {reserva.hora:%H:%M}'


def _cuerpo_html(reserva):
    pendiente = ''
    if reserva.forma_pago == reserva.FormaPago.ANTICIPO and reserva.precio_total and reserva.monto_pagado:
        restante = reserva.precio_total - reserva.monto_pagado
        pendiente = (
            f'<p>Pagaste tu anticipo de {reserva.monto_pagado} {reserva.moneda}. '
            f'Quedan {restante} {reserva.moneda} por liquidar en efectivo el dia del viaje.</p>'
        )

    lunch = (
        f'<li><strong>Lunch:</strong> {reserva.numero_personas} (incluido en tu pago)</li>'
        if reserva.lleva_lunch else ''
    )

    # Aviso explicito: si el cliente cree que su traslado ya esta pagado, el
    # problema aparece el dia del viaje y en el muelle.
    por_cotizar = ''
    if reserva.tiene_cotizaciones_pendientes:
        pedidos = [
            etiqueta for pedido, etiqueta in
            ((reserva.pide_bebidas, 'bebidas'), (reserva.pide_transporte, 'transporte'))
            if pedido
        ]
        por_cotizar = (
            f'<p><strong>Pediste {" y ".join(pedidos)}.</strong> Eso <strong>no</strong> esta '
            f'incluido en el monto que acabas de pagar: su precio depende de lo que elijas y de '
            f'la distancia, asi que nuestro agente te lo cotiza y lo acuerdas directamente con el.</p>'
        )

    return (
        f'<p>Hola {reserva.nombre_cliente}, tu reserva quedo confirmada.</p>'
        f'<ul>'
        f'<li><strong>Fecha:</strong> {reserva.fecha}</li>'
        f'<li><strong>Hora de salida:</strong> {reserva.hora:%H:%M}</li>'
        f'<li><strong>Personas:</strong> {reserva.numero_personas}</li>'
        f'{lunch}'
        f'<li><strong>Punto de encuentro:</strong> {PUNTO_DE_ENCUENTRO}</li>'
        f'</ul>'
        f'{pendiente}'
        f'{por_cotizar}'
        f'<p>Un agente te contacta en las proximas 24 horas antes del viaje con los '
        f'detalles de ubicacion, traslado y el nombre de tu capitan.</p>'
    )


def enviar_correo_confirmacion(reserva):
    """Correo de confirmacion via Resend. Devuelve True si se mando.

    Si `RESEND_BCC` esta configurado, el negocio recibe copia oculta de cada
    confirmacion. Ver el comentario de ese setting en config/settings/base.py.
    """
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando correo de la reserva %s', reserva.pk)
        return False

    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [reserva.correo_cliente],
        'subject': _asunto(reserva),
        'html': _cuerpo_html(reserva),
    }

    # Copia al negocio, solo si esta configurada. Se omite la clave entera cuando
    # no hay direcciones en vez de mandar una lista vacia: Resend la aceptaria,
    # pero deja el cuerpo de la peticion mas limpio de leer en sus logs.
    if settings.RESEND_BCC:
        cuerpo['bcc'] = settings.RESEND_BCC

    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json=cuerpo,
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception('Fallo el correo de confirmacion de la reserva %s', reserva.pk)
        return False
    return True


def enviar_whatsapp_confirmacion(reserva):
    """Confirmacion por WhatsApp Business API. Manda una plantilla aprobada
    (`WHATSAPP_TEMPLATE`) con fecha, hora y personas como parametros, porque
    fuera de la ventana de 24 horas Meta no acepta texto libre."""
    if not (settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID):
        logger.info('WhatsApp sin configurar, no se mando mensaje de la reserva %s', reserva.pk)
        return False

    parametros = [
        reserva.nombre_cliente,
        str(reserva.fecha),
        f'{reserva.hora:%H:%M}',
        str(reserva.numero_personas),
    ]

    try:
        response = requests.post(
            f'https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages',
            headers={'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}'},
            json={
                'messaging_product': 'whatsapp',
                'to': reserva.telefono_cliente,
                'type': 'template',
                'template': {
                    'name': settings.WHATSAPP_TEMPLATE,
                    'language': {'code': settings.WHATSAPP_TEMPLATE_LANG},
                    'components': [{
                        'type': 'body',
                        'parameters': [{'type': 'text', 'text': p} for p in parametros],
                    }],
                },
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception('Fallo el WhatsApp de confirmacion de la reserva %s', reserva.pk)
        return False
    return True


def notificar_reserva_pagada(reserva):
    """Punto de entrada unico desde el webhook de pago. Nunca lanza."""
    return {
        'email': enviar_correo_confirmacion(reserva),
        'whatsapp': enviar_whatsapp_confirmacion(reserva),
    }
