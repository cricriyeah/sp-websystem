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

from apps.fleet.enums import TipoServicio

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


def _es_traslado(reserva):
    return bool(reserva.servicio_id and reserva.servicio.tipo_servicio == TipoServicio.TRANSPORTE)


def _cuerpo_traslado_html(reserva):
    detalle = reserva.detalle_transporte
    punto = detalle.punto_encuentro.nombre if detalle.punto_encuentro_id else detalle.direccion_personalizada
    regreso = (
        f'<li><strong>Fecha de regreso al aeropuerto:</strong> {detalle.fecha_regreso}</li>'
        if detalle.fecha_regreso else ''
    )
    personas = detalle.numero_personas if detalle.numero_personas is not None else reserva.numero_personas
    return (
        f'<p>Hola {_html(reserva.nombre_cliente)}, tu traslado quedo confirmado.</p>'
        f'<ul>'
        f'<li><strong>Tipo de traslado:</strong> {_html(detalle.get_tipo_traslado_display())}</li>'
        f'<li><strong>Fecha:</strong> {reserva.fecha}</li>'
        f'<li><strong>Hora:</strong> {reserva.hora:%H:%M}</li>'
        f'{regreso}'
        f'<li><strong>Personas:</strong> {personas}</li>'
        f'<li><strong>Punto de encuentro:</strong> {_html(punto)}</li>'
        f'</ul>'
    )


def _cuerpo_html(reserva):
    if _es_traslado(reserva):
        return _cuerpo_traslado_html(reserva)

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
    lineas_personalizaciones = []
    filas = (reserva.personalizaciones_seleccionadas.select_related(
        'servicio_personalizacion__personalizacion') if reserva.pk else [])
    for fila in filas:
        personalizacion = fila.servicio_personalizacion.personalizacion
        if personalizacion.tipo_interaccion != 'check' or fila.subtotal is None:
            continue
        lineas_personalizaciones.append(
            f'<li><strong>{_html(personalizacion.nombre)}:</strong> {fila.cantidad} '
            f'— {fila.subtotal:.2f} {_html(reserva.moneda)} (incluido en tu pago)</li>')
    extras = ''.join(lineas_personalizaciones)

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
        f'<li><strong>Fecha:</strong> {reserva.fecha_inicio_paquete}</li>'
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
    # La plantilla vigente describe pesca. Transporte se confirma por correo
    # hasta contar con una plantilla de Meta propia, fuera del alcance de SP1.
    if _es_traslado(reserva):
        return False
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


def _cuerpo_orden_html(orden, reservas):
    componentes_html = []
    for r in reservas:
        if _es_traslado(r):
            detalle = getattr(r, 'detalle_transporte', None)
            tipo = detalle.get_tipo_traslado_display() if detalle else 'Traslado'
            punto = (
                detalle.punto_encuentro.nombre if (detalle and detalle.punto_encuentro_id)
                else (detalle.direccion_personalizada if detalle else PUNTO_DE_ENCUENTRO)
            )
            regreso = (
                f'<li><strong>Fecha de regreso al aeropuerto:</strong> {detalle.fecha_regreso}</li>'
                if (detalle and detalle.fecha_regreso) else ''
            )
            personas = (
                detalle.numero_personas if (detalle and detalle.numero_personas is not None)
                else r.numero_personas
            )
            comp = (
                f'<li><strong>Traslado ({_html(tipo)}):</strong>'
                f'<ul>'
                f'<li><strong>Fecha:</strong> {r.fecha}</li>'
                f'<li><strong>Hora:</strong> {r.hora:%H:%M}</li>'
                f'{regreso}'
                f'<li><strong>Personas:</strong> {personas}</li>'
                f'<li><strong>Punto de encuentro:</strong> {_html(punto)}</li>'
                f'</ul></li>'
            )
        else:
            nombre_servicio = r.servicio.nombre if r.servicio else 'Pesca'
            comp = (
                f'<li><strong>{_html(nombre_servicio)}:</strong>'
                f'<ul>'
                f'<li><strong>Fecha:</strong> {r.fecha}</li>'
                f'<li><strong>Hora:</strong> {r.hora:%H:%M}</li>'
                f'<li><strong>Personas:</strong> {r.numero_personas}</li>'
                f'<li><strong>Punto de encuentro:</strong> {PUNTO_DE_ENCUENTRO}</li>'
                f'</ul></li>'
            )
        componentes_html.append(comp)

    paquete_nombre = orden.paquete.nombre if orden.paquete_id else 'Paquete'
    return (
        f'<p>Hola {_html(orden.nombre_cliente)}, tu paquete {_html(paquete_nombre)} quedo confirmado.</p>'
        f'<p>Detalle de tus servicios:</p>'
        f'<ul>{"".join(componentes_html)}</ul>'
        f'<p>Te esperamos para vivir una gran experiencia.</p>'
    )


def enviar_correo_orden(orden, reservas):
    """Correo combinado de orden vía Resend. Devuelve True si se mandó."""
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando correo de la orden %s', orden.pk)
        return False

    paquete_nombre = orden.paquete.nombre if orden.paquete_id else 'Paquete'
    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [orden.correo_cliente],
        'subject': f'Reserva confirmada — {paquete_nombre}',
        'html': _cuerpo_orden_html(orden, reservas),
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
        logger.exception('Fallo el correo de confirmacion de la orden %s', orden.pk)
        return False
    return True


def notificar_orden_pagada(orden):
    """Punto de entrada único desde el webhook al cerrarse una Orden cruza-empresa. Nunca lanza."""
    try:
        from django.db import connection
        from apps.bookings.models import Reserva
        from apps.bookings.orden_lectura import reservas_de_orden
        from apps.tenancy import scope
        from apps.tenancy.models import Empresa

        filas = reservas_de_orden(orden.pk)
        if not filas:
            return {'email': False, 'whatsapp': []}

        prev_alcance = getattr(connection, 'alcance_actual', None)
        connection.alcance_actual = None
        reservas = []
        try:
            # El último webhook puede pertenecer al proveedor de transporte;
            # el paquete solo es visible bajo la empresa líder.
            from apps.fleet.models import Paquete
            lider = Empresa.objects.get(pk=orden.empresa_lider_id)
            with scope.con_empresa(lider):
                orden.paquete = Paquete.objects.get(pk=orden.paquete_id)
            for fila in filas:
                empresa = Empresa.objects.get(pk=fila['empresa_id'])
                with scope.con_empresa(empresa):
                    reserva = (
                        Reserva.objects.select_related(
                            'servicio',
                            'detalle_transporte',
                            'detalle_transporte__punto_encuentro',
                            'empresa',
                        )
                        .get(pk=fila['reserva_id'])
                    )
                    reservas.append(reserva)
        finally:
            connection.alcance_actual = prev_alcance
            if connection.vendor == 'postgresql' and prev_alcance:
                with connection.cursor() as cursor:
                    if prev_alcance[0] == 'empresa':
                        cursor.execute(f'SET LOCAL app.current_empresa_id = {int(prev_alcance[1])}')
                    elif prev_alcance[0] == 'operador':
                        cursor.execute("SET LOCAL app.operador_plataforma = 'on'")

        # 1. Correo combinado
        email_enviado = False
        try:
            email_enviado = enviar_correo_orden(orden, reservas)
        except Exception:
            logger.exception('Fallo inesperado al enviar correo de la orden %s', orden.pk)

        # 2. WhatsApp por empresa (una llamada por reserva)
        wa_resultados = []
        prev_alcance = getattr(connection, 'alcance_actual', None)
        connection.alcance_actual = None
        try:
            for r in reservas:
                try:
                    with scope.con_empresa(r.empresa):
                        wa_enviado = enviar_whatsapp_confirmacion(r)
                        wa_resultados.append(wa_enviado)
                except Exception:
                    logger.exception(
                        'Fallo inesperado al enviar whatsapp de reserva %s de orden %s',
                        r.pk,
                        orden.pk,
                    )
                    wa_resultados.append(False)
        finally:
            connection.alcance_actual = prev_alcance
            if connection.vendor == 'postgresql' and prev_alcance:
                with connection.cursor() as cursor:
                    if prev_alcance[0] == 'empresa':
                        cursor.execute(f'SET LOCAL app.current_empresa_id = {int(prev_alcance[1])}')
                    elif prev_alcance[0] == 'operador':
                        cursor.execute("SET LOCAL app.operador_plataforma = 'on'")

        return {'email': email_enviado, 'whatsapp': wa_resultados}
    except Exception:
        logger.exception('Error no controlado en notificar_orden_pagada para orden %s', getattr(orden, 'pk', None))
        return {'email': False, 'whatsapp': []}
