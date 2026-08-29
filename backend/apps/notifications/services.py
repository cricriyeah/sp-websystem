"""Confirmacion automatica al cliente cuando entra el pago.

Dos canales, ambos por HTTP y ambos opcionales: correo (Resend) y WhatsApp
(WhatsApp Business API de Meta). Cada uno se activa solo si sus variables de
entorno estan puestas — igual que Stripe, en local no hay llaves y no se manda
nada. Ninguna falla de notificacion debe tumbar el cobro: el webhook de Stripe
ya recibio el dinero, asi que todo error se registra y se sigue.
"""
import logging
from html import escape

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 10

PUNTO_DE_ENCUENTRO = 'Marina La Costa, Rangel y Navarro, La Paz, BCS'


def _html(valor):
    """Escapa un dato escrito por una persona antes de meterlo al correo.

    Los cuerpos se arman con f-strings, asi que aqui no hay un motor de
    plantillas que escape solo. Y `validar_nombre_persona` es permisivo a
    proposito —acepta acentos, apostrofos y guiones porque son parte de nombres
    reales, y solo rechaza digitos—, asi que `<` y `>` pasan: sin esto, un
    nombre como `Ana <a href="https://malo.tld">Ver reserva</a>` llega
    renderizado al cliente y, por `RESEND_BCC`, tambien al buzon del negocio.

    Se escapa al usar el dato y no al guardarlo: en la base tiene que quedar lo
    que la persona escribio, que es lo que la vendedora lee y corrige.
    """
    return escape(str(valor))


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

    # Lo que compro en el checkout (brunch, licencia, carnada): ya tiene precio
    # congelado porque este correo solo se manda despues de pagar. `reserva.pk`
    # se checa aparte porque en produccion siempre existe (este correo solo se
    # dispara desde una reserva ya guardada y pagada) pero las pruebas de
    # renderizado del correo usan una `Reserva` en memoria sin guardar, y
    # consultar una relacion inversa sin pk revienta con ValueError, no con
    # AttributeError — `getattr(..., None)` no lo atrapa.
    extras = ''.join(
        f'<li><strong>{_html(extra.extras_item.nombre)}:</strong> {extra.cantidad} '
        f'(incluido en tu pago)</li>'
        for extra in (reserva.extras_seleccionados.select_related('extras_item') if reserva.pk else [])
    )

    # El punto de encuentro real si compro traslado; si no, el general.
    transporte = reserva.transporte if reserva.pk and hasattr(reserva, 'transporte') else None
    if transporte:
        lugar = transporte.punto_encuentro.nombre if transporte.punto_encuentro else transporte.direccion_personalizada
        punto_de_encuentro = f'{_html(lugar)} (incluye tu traslado, ya pagado)'
    else:
        punto_de_encuentro = PUNTO_DE_ENCUENTRO

    # Aviso explicito: si el cliente cree que algo ya esta pagado sin estarlo,
    # el problema aparece el dia del viaje.
    por_cotizar = ''
    if reserva.tiene_cotizaciones_pendientes:
        pedidos = [
            etiqueta for pedido, etiqueta in
            ((reserva.pide_bebidas, 'bebidas'), (reserva.pide_extras_whatsapp, 'extras'))
            if pedido
        ]
        por_cotizar = (
            f'<p><strong>Pediste {" y ".join(pedidos)}.</strong> Eso <strong>no</strong> esta '
            f'incluido en el monto que acabas de pagar: nuestro agente te lo cotiza y lo '
            f'acuerdas directamente con el.</p>'
        )

    return (
        f'<p>Hola {_html(reserva.nombre_cliente)}, tu reserva quedo confirmada.</p>'
        f'<ul>'
        f'<li><strong>Fecha:</strong> {reserva.fecha}</li>'
        f'<li><strong>Hora de salida:</strong> {reserva.hora:%H:%M}</li>'
        f'<li><strong>Personas:</strong> {reserva.numero_personas}</li>'
        f'{extras}'
        f'<li><strong>Punto de encuentro:</strong> {punto_de_encuentro}</li>'
        f'</ul>'
        f'{pendiente}'
        f'{por_cotizar}'
        f'<p>Te llega un segundo correo con el nombre de tu capitan y la panga que '
        f'les toca, en cuanto queden asignados.</p>'
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


def _asunto_asignacion(reserva):
    return f'Tu capitan y tu panga — {reserva.fecha} {reserva.hora:%H:%M}'


def _cuerpo_asignacion_html(reserva):
    """Lo que el cliente necesita el dia del viaje, y nada mas.

    El telefono del capitan NO va aqui a proposito: el capitan sale de madrugada
    y no puede estar contestando dudas de clientes a cualquier hora. Todo pasa
    por el numero del negocio, que es el que si tiene quien lo atienda.
    """
    pendiente = ''
    if reserva.forma_pago == reserva.FormaPago.ANTICIPO and reserva.precio_total and reserva.monto_pagado:
        restante = reserva.precio_total - reserva.monto_pagado
        pendiente = (
            f'<p>Recuerda que llevas {restante} {reserva.moneda} por liquidar en efectivo '
            f'el dia del viaje.</p>'
        )

    return (
        f'<p>Hola {_html(reserva.nombre_cliente)}, ya sabemos con quien sales.</p>'
        f'<ul>'
        f'<li><strong>Capitan:</strong> {_html(reserva.capitan.nombre)}</li>'
        f'<li><strong>Panga:</strong> {_html(reserva.embarcacion.nombre)}</li>'
        f'<li><strong>Fecha:</strong> {reserva.fecha}</li>'
        f'<li><strong>Hora de salida:</strong> {reserva.hora:%H:%M}</li>'
        f'<li><strong>Punto de encuentro:</strong> {PUNTO_DE_ENCUENTRO}</li>'
        f'</ul>'
        f'{pendiente}'
        f'<p>Llega 15 minutos antes de la hora de salida. Si algo cambia de tu lado, '
        f'escribenos por WhatsApp y lo movemos.</p>'
    )


def enviar_correo_asignacion(reserva):
    """Segundo correo: con que capitan y en que panga sale el cliente.

    Se manda aparte del de confirmacion porque los dos datos no existen cuando
    entra el pago — la panga y el capitan se reparten despues, desde la agenda
    del admin. Devuelve True si se mando.
    """
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando el aviso de asignacion %s', reserva.pk)
        return False

    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [reserva.correo_cliente],
        'subject': _asunto_asignacion(reserva),
        'html': _cuerpo_asignacion_html(reserva),
    }
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
        logger.exception('Fallo el aviso de asignacion de la reserva %s', reserva.pk)
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
