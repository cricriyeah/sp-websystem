"""Confirmacion automatica al cliente cuando entra el pago.

Dos canales, ambos por HTTP y ambos opcionales: correo (Resend) y WhatsApp
(WhatsApp Business API de Meta). Cada uno se activa solo si sus variables de
entorno estan puestas — igual que Stripe, en local no hay llaves y no se manda
nada. Ninguna falla de notificacion debe tumbar el cobro: el webhook de Stripe
ya recibio el dinero, asi que todo error se registra y se sigue.
"""
import logging
from html import escape
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from apps.fleet.enums import TipoServicio

from . import plantilla

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 10

# Lo que dice el correo cuando el servicio no tiene capturado de donde sale el cliente. Antes
# habia un lugar fijo en el codigo que salia en los correos de TODAS las empresas; no se
# inventa uno: el aviso a la vendedora es la columna «Sales de» de la lista de Servicios.
SIN_PUNTO_DE_ENCUENTRO = 'Te lo confirmamos por WhatsApp'


def punto_de_encuentro(reserva):
    """De donde sale el cliente, como lo escribio el jefe en el servicio; '' si no lo capturo.

    Es `Servicio.punto_salida` (el «Sales de» de la ficha): el mismo dato que ve el cliente en
    el sitio, para que correo y sitio no puedan decir cosas distintas.
    """
    if not reserva.servicio_id:
        return ''
    return (reserva.servicio.punto_salida or '').strip()


def _renglon_punto_de_encuentro(reserva):
    """El renglon «Punto de encuentro» del correo, o '' si no aplica.

    Un hospedaje sin dato no lleva renglon (llegar a un hotel no es encontrarse en un
    muelle); el resto dice que se confirma por WhatsApp en vez de afirmar un lugar.
    """
    punto = punto_de_encuentro(reserva)
    if not punto:
        if reserva.servicio_id and reserva.servicio.tipo_servicio == TipoServicio.HOSPEDAJE:
            return ''
        punto = SIN_PUNTO_DE_ENCUENTRO
    return f'<li><strong>Punto de encuentro:</strong> {_html(punto)}</li>'


def _motivo_http(error):
    """Lo que respondio el proveedor, para el log.

    `raise_for_status()` solo dice "403 Forbidden" y descarta el cuerpo, que es
    donde Resend y Meta explican por que rechazaron el envio (dominio sin
    verificar, destinatario no permitido, llave sin permiso...). Sin esto, un
    fallo de configuracion se queda en adivinanzas.
    """
    respuesta = getattr(error, 'response', None)
    if respuesta is None:
        return str(error)
    return (respuesta.text or '')[:300]


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


def hora_texto(reserva):
    """La hora de salida, o 'por definir' si la reserva no la tiene (paquete que no la pide)."""
    return reserva.hora.strftime('%H:%M') if reserva.hora else 'por definir'


def _folio(reserva):
    return f' #{reserva.pk}' if reserva.pk else ''


def _asunto(reserva):
    # El folio en el asunto: es lo que el cliente busca en su bandeja cuando necesita escribirnos.
    return f'Reserva confirmada{_folio(reserva)} — {reserva.fecha} {hora_texto(reserva)}'


def _es_traslado(reserva):
    return bool(reserva.servicio_id and reserva.servicio.tipo_servicio == TipoServicio.TRANSPORTE)


def _empresa_de(reserva):
    return reserva.empresa.nombre if reserva.empresa_id else 'Sun Baja Experience'


def _par_punto_de_encuentro(reserva, etiqueta='Punto de encuentro'):
    """(etiqueta, texto) del renglon del punto de encuentro, o None si no aplica (ver `_renglon_punto_de_encuentro`)."""
    punto = punto_de_encuentro(reserva)
    if not punto:
        if reserva.servicio_id and reserva.servicio.tipo_servicio == TipoServicio.HOSPEDAJE:
            return None
        punto = SIN_PUNTO_DE_ENCUENTRO
    return (etiqueta, _html(punto))


def _dia_y_hora(fecha, hora):
    """Los dos primeros renglones de «Lo que reservaste»: el día y, si se sabe, la hora."""
    pares = [('Día', plantilla.dia_largo(fecha))]
    if hora:
        pares.append(('Hora', plantilla.hora_12(hora)))
    return pares


def _cuerpo_traslado_html(reserva):
    detalle = reserva.detalle_transporte
    punto = detalle.punto_encuentro.nombre if detalle.punto_encuentro_id else detalle.direccion_personalizada
    personas = detalle.numero_personas if detalle.numero_personas is not None else reserva.numero_personas
    return plantilla.correo(
        actividad='traslado', empresa=_empresa_de(reserva), titulo='Traslado confirmado', folio=reserva.pk,
        producto=_html(reserva.servicio.nombre),
        previa=f'{reserva.fecha} · {hora_texto(reserva)}',
        intro_html=f'Hola {_html(reserva.nombre_cliente)}, tu traslado quedó confirmado.',
        pares=_dia_y_hora(reserva.fecha, reserva.hora) + [
            ('Tipo de traslado', _html(detalle.get_tipo_traslado_display())),
            ('Fecha de regreso al aeropuerto', str(detalle.fecha_regreso) if detalle.fecha_regreso else ''),
            ('Personas', str(personas)),
            ('Punto de encuentro', _html(punto)),
        ],
    )


def _saldo_en_efectivo(reserva):
    if reserva.forma_pago == reserva.FormaPago.ANTICIPO and reserva.precio_total and reserva.monto_pagado:
        restante = reserva.saldo_pendiente
        if restante > 0:
            return restante
    return None


def _bloques_de_dinero(reserva, pendiente):
    """«El dinero» como en el sitio: el bloque tinta de lo pagado hoy y, si hay saldo, el de lo que queda en efectivo."""
    if not reserva.monto_pagado:
        return ''
    html = plantilla.bloque_pagado(f'{reserva.monto_pagado} {reserva.moneda}')
    if pendiente:
        html += plantilla.bloque_resto(
            f'Quedan {pendiente} {_html(reserva.moneda)} por liquidar en efectivo el día del viaje.')
    return html


def _cuerpo_html(reserva):
    if _es_traslado(reserva):
        return _cuerpo_traslado_html(reserva)

    actividad = plantilla.actividad_de(reserva)
    fecha = reserva.fecha_inicio_paquete

    # Lo que compro en el checkout (brunch, licencia, carnada): ya tiene precio
    # congelado porque este correo solo se manda despues de pagar. `reserva.pk`
    # se checa aparte porque en produccion siempre existe (este correo solo se
    # dispara desde una reserva ya guardada y pagada) pero las pruebas de
    # renderizado del correo usan una `Reserva` en memoria sin guardar, y
    # consultar una relacion inversa sin pk revienta con ValueError, no con
    # AttributeError — `getattr(..., None)` no lo atrapa.
    pares = _dia_y_hora(fecha, reserva.hora)
    if reserva.hora and actividad == 'mar':
        pares.append(('Llega a las', plantilla.hora_12(plantilla.quince_antes(reserva.hora)) + ' (15 minutos antes)'))
    punto = _par_punto_de_encuentro(reserva, 'Sales de' if actividad == 'mar' else 'Punto de encuentro')
    if punto:
        pares.append(punto)
    pares.append(('Personas', str(reserva.numero_personas)))
    filas_extras = (reserva.personalizaciones_seleccionadas.select_related(
        'servicio_personalizacion__personalizacion') if reserva.pk else [])
    for fila in filas_extras:
        personalizacion = fila.servicio_personalizacion.personalizacion
        if personalizacion.tipo_interaccion != 'check' or fila.subtotal is None:
            continue
        pares.append((
            _html(personalizacion.nombre),
            f'{fila.cantidad} — {fila.subtotal:.2f} {_html(reserva.moneda)} (incluido en tu pago)',
        ))

    # Aviso explicito: si el cliente cree que algo ya esta pagado sin estarlo,
    # el problema aparece el dia del viaje.
    siguiente = ''
    if reserva.tiene_cotizaciones_pendientes:
        pedidos = [
            etiqueta for pedido, etiqueta in
            ((reserva.pide_bebidas, 'bebidas'), (reserva.pide_extras_whatsapp, 'extras'))
            if pedido
        ]
        siguiente += plantilla.recuadro(
            f'<strong>Pediste {" y ".join(pedidos)}.</strong> Eso <strong>no</strong> está '
            f'incluido en el monto que acabas de pagar: nuestro agente te lo cotiza y lo '
            f'acuerdas directamente con él.'
        )
    if actividad == 'mar':
        siguiente += plantilla.parrafo('Te llega otro correo con el nombre de tu capitán y la panga que les toca, '
                                       'en cuanto queden asignados.', plantilla.TINTA, 16)

    return plantilla.correo(
        actividad=actividad, empresa=_empresa_de(reserva), titulo='Reserva confirmada', folio=reserva.pk,
        producto=_html(reserva.servicio.nombre) if reserva.servicio_id else '',
        previa=f'{fecha} · {hora_texto(reserva)}',
        intro_html=f'Hola {_html(reserva.nombre_cliente)}, tu reserva quedó confirmada.',
        pares=pares, dinero_html=_bloques_de_dinero(reserva, _saldo_en_efectivo(reserva)),
        siguiente_html=siguiente, con_garantias=(actividad == 'mar'),
    )


def enviar_correo_confirmacion(reserva):
    """Correo de confirmacion via Resend. Devuelve True si se mando.

    Si `RESEND_BCC` esta configurado, el negocio recibe copia oculta de cada
    confirmacion. Ver el comentario de ese setting en config/settings/base.py.
    """
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando correo de la reserva %s', reserva.pk)
        return False

    _html_correo = _cuerpo_html(reserva)
    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [reserva.correo_cliente],
        'subject': _asunto(reserva),
        'html': _html_correo,
        'text': plantilla.a_texto(_html_correo),
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
    except requests.RequestException as error:
        logger.exception('Fallo el correo de confirmacion de la reserva %s: %s', reserva.pk, _motivo_http(error))
        return False
    return True


def _asunto_asignacion(reserva):
    return f'Tu capitán y tu panga{_folio(reserva)} — {reserva.fecha} {hora_texto(reserva)}'


def _cuerpo_asignacion_html(reserva):
    """Lo que el cliente necesita el dia del viaje, y nada mas.

    El telefono del capitan NO va aqui a proposito: el capitan sale de madrugada
    y no puede estar contestando dudas de clientes a cualquier hora. Todo pasa
    por el numero del negocio, que es el que si tiene quien lo atienda.
    """
    pendiente = _saldo_en_efectivo(reserva)
    dinero = ''
    if pendiente:
        dinero = plantilla.bloque_resto(
            f'Recuerda que llevas {pendiente} {_html(reserva.moneda)} por liquidar en efectivo el día del viaje.')
    primer_nombre = (reserva.capitan.nombre.split() or [''])[0]
    pares = [('Día', plantilla.dia_largo(reserva.fecha))]
    if reserva.hora:
        pares.append(('Llega a las', plantilla.hora_12(plantilla.quince_antes(reserva.hora)) + ' (15 minutos antes)'))
        pares.append(('Hora de salida', plantilla.hora_12(reserva.hora)))
    pares += [('Capitán', _html(reserva.capitan.nombre)), ('Panga', _html(reserva.embarcacion.nombre))]
    punto = _par_punto_de_encuentro(reserva, 'Sales de')
    if punto:
        pares.append(punto)
    return plantilla.correo(
        actividad=plantilla.actividad_de(reserva), empresa=_empresa_de(reserva),
        titulo=f'Sales con {primer_nombre}', folio=reserva.pk,
        producto=_html(reserva.servicio.nombre) if reserva.servicio_id else '',
        previa=f'{reserva.fecha} · {hora_texto(reserva)} · sale con {reserva.capitan.nombre}',
        intro_html=f'Hola {_html(reserva.nombre_cliente)}, ya sabemos con quién sales.',
        pares=pares, etiqueta_pares='Tu salida', dinero_html=dinero,
        siguiente_html=plantilla.parrafo(
            'Llega 15 minutos antes de la hora de salida. Si algo cambia de tu lado, '
            'escríbenos por WhatsApp y lo movemos.', plantilla.TINTA, 16),
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

    _html_correo = _cuerpo_asignacion_html(reserva)
    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [reserva.correo_cliente],
        'subject': _asunto_asignacion(reserva),
        'html': _html_correo,
        'text': plantilla.a_texto(_html_correo),
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
    except requests.RequestException as error:
        logger.exception('Fallo el aviso de asignacion de la reserva %s: %s', reserva.pk, _motivo_http(error))
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
        f'{hora_texto(reserva)}',
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
    except requests.RequestException as error:
        logger.exception('Fallo el WhatsApp de confirmacion de la reserva %s: %s', reserva.pk, _motivo_http(error))
        return False
    return True


def _cuerpo_aviso_empresa_html(reserva):
    """Lo que necesita la empresa para saber que le entro una reserva y a quien
    hablarle. Solo lo de su propio componente: en un paquete de dos empresas cada
    una recibe su aviso con su parte, no el desglose de dinero de la otra."""
    producto = reserva.servicio.nombre if reserva.servicio_id else (
        reserva.paquete.nombre if reserva.paquete_id else 'Reserva')
    detalle = ''
    if _es_traslado(reserva) and hasattr(reserva, 'detalle_transporte'):
        d = reserva.detalle_transporte
        punto = d.punto_encuentro.nombre if d.punto_encuentro_id else d.direccion_personalizada
        regreso = f'<li><strong>Regreso:</strong> {d.fecha_regreso}</li>' if d.fecha_regreso else ''
        detalle = (
            f'<li><strong>Traslado:</strong> {_html(d.get_tipo_traslado_display())}</li>'
            f'<li><strong>Punto de encuentro:</strong> {_html(punto)}</li>{regreso}'
        )
    pago = ''
    if reserva.monto_pagado:
        pago = f'<li><strong>Pagado en linea:</strong> {reserva.monto_pagado} {_html(reserva.moneda)}</li>'
    saldo = reserva.saldo_pendiente
    if saldo and saldo > 0:
        pago += f'<li><strong>Saldo por cobrar:</strong> {saldo} {_html(reserva.moneda)}</li>'
    return (
        f'<p>Entro una reserva pagada para {_html(reserva.empresa.nombre)}.</p>'
        f'<ul>'
        f'<li><strong>Servicio:</strong> {_html(producto)}</li>'
        f'<li><strong>Fecha:</strong> {reserva.fecha}</li>'
        f'<li><strong>Hora:</strong> {hora_texto(reserva)}</li>'
        f'<li><strong>Personas:</strong> {reserva.numero_personas}</li>'
        f'{detalle}'
        f'<li><strong>Cliente:</strong> {_html(reserva.nombre_cliente)}</li>'
        f'<li><strong>Telefono:</strong> {_html(reserva.telefono_cliente)}</li>'
        f'<li><strong>Correo:</strong> {_html(reserva.correo_cliente)}</li>'
        f'{pago}'
        f'<li><strong>Folio:</strong> #{reserva.pk}</li>'
        f'</ul>'
    )


def enviar_aviso_empresa(reserva):
    """Avisa a la empresa duena de la reserva que entro una pagada. True si se mando.

    Los destinatarios son `Empresa.correos_aviso`; sin ellos no hace nada. Va aparte
    de `RESEND_BCC` (una copia global de todo al negocio): esto es por empresa, para
    que cada una se entere de lo suyo. Responder al correo le contesta al cliente.
    """
    destinatarios = reserva.empresa.lista_correos_aviso()
    if not destinatarios:
        return False
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando el aviso a la empresa de la reserva %s', reserva.pk)
        return False

    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json={
                'from': settings.RESEND_FROM,
                'to': destinatarios,
                'reply_to': reserva.correo_cliente,
                'subject': f'Nueva reserva — {reserva.fecha} {hora_texto(reserva)} · {reserva.nombre_cliente}',
                'html': _cuerpo_aviso_empresa_html(reserva),
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.exception('Fallo el aviso a la empresa de la reserva %s: %s', reserva.pk, _motivo_http(error))
        return False
    return True


def notificar_reserva_pagada(reserva):
    """Punto de entrada unico desde el webhook de pago. Nunca lanza."""
    resultado = {
        'email': enviar_correo_confirmacion(reserva),
        'whatsapp': enviar_whatsapp_confirmacion(reserva),
    }
    try:
        resultado['empresa'] = enviar_aviso_empresa(reserva)
    except Exception:
        logger.exception('Fallo inesperado al avisar a la empresa de la reserva %s', reserva.pk)
        resultado['empresa'] = False
    return resultado


def _cuerpo_orden_html(orden, reservas):
    componentes_html = []
    for r in reservas:
        if _es_traslado(r):
            detalle = getattr(r, 'detalle_transporte', None)
            tipo = detalle.get_tipo_traslado_display() if detalle else 'Traslado'
            punto = (
                detalle.punto_encuentro.nombre if (detalle and detalle.punto_encuentro_id)
                else (detalle.direccion_personalizada if detalle else SIN_PUNTO_DE_ENCUENTRO)
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
                f'<li><strong>Hora:</strong> {hora_texto(r)}</li>'
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
                f'<li><strong>Hora:</strong> {hora_texto(r)}</li>'
                f'<li><strong>Personas:</strong> {r.numero_personas}</li>'
                f'{_renglon_punto_de_encuentro(r)}'
                f'</ul></li>'
            )
        componentes_html.append(comp)

    paquete_nombre = orden.paquete.nombre if orden.paquete_id else 'Paquete'
    empresa = orden.empresa_lider.nombre if orden.empresa_lider_id else 'Sun Baja Experience'
    detalle = (
        f'<ul style="margin:0;padding-left:20px;font:400 16px/1.6 {plantilla.CUERPO};color:{plantilla.TINTA};">'
        + "".join(componentes_html) + '</ul>'
    )
    return plantilla.correo(
        actividad='mar', empresa=empresa, titulo='Reserva confirmada', folio=orden.pk, producto=_html(paquete_nombre),
        previa=paquete_nombre,
        intro_html=f'Hola {_html(orden.nombre_cliente)}, tu paquete {_html(paquete_nombre)} quedó confirmado.',
        siguiente_html=detalle + plantilla.parrafo('Te esperamos para vivir una gran experiencia.'),
    )


def enviar_correo_orden(orden, reservas):
    """Correo combinado de orden vía Resend. Devuelve True si se mandó."""
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando correo de la orden %s', orden.pk)
        return False

    paquete_nombre = orden.paquete.nombre if orden.paquete_id else 'Paquete'
    _html_correo = _cuerpo_orden_html(orden, reservas)
    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [orden.correo_cliente],
        'subject': f'Reserva confirmada #{orden.pk} — {paquete_nombre}',
        'html': _html_correo,
        'text': plantilla.a_texto(_html_correo),
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
    except requests.RequestException as error:
        logger.exception('Fallo el correo de confirmacion de la orden %s: %s', orden.pk, _motivo_http(error))
        return False
    return True


def enlace_retomar_orden(orden, lang='es'):
    """Enlace con la sede requerida por /[lang]/reservar y el UUID de la orden."""
    base = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    if not base or not orden.checkout_id:
        return ''
    from apps.tenancy import scope

    with scope.con_empresa(orden.empresa_lider):
        paquete_slug = orden.paquete.slug
    query = urlencode({
        'paquete': paquete_slug,
        'sede': orden.sede.slug,
        'retomar': str(orden.checkout_id),
    })
    return f'{base}/{lang}/reservar?{query}'


def enviar_correo_retomar_orden(orden):
    """Avisa que falta un pago, sin afirmar que la reserva ya esté confirmada."""
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        return False
    enlace = enlace_retomar_orden(orden)
    if not enlace:
        return False
    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [orden.correo_cliente],
        'subject': 'Tu reserva sigue abierta: falta un pago',
        'html': (
            f'<p>Hola {_html(orden.nombre_cliente)}, tu reserva sigue abierta y falta terminar el pago.</p>'
            f'<p>El primer pago está retenido en tu tarjeta; aún no se ha cobrado.</p>'
            f'<p><a href="{escape(enlace, quote=True)}">Continuar reservación</a></p>'
        ),
    }
    if settings.RESEND_BCC:
        cuerpo['bcc'] = settings.RESEND_BCC
    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json=cuerpo, timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.exception('Fallo el correo de retomar de la orden %s: %s', orden.pk, _motivo_http(error))
        return False
    return True


def notificar_orden_retenida(orden, reservas_info):
    """Sella una sola notificación cuando un pago está retenido y otro pendiente."""
    from apps.bookings.models import Orden
    from apps.tenancy import scope

    estados = [fila['pago']['estado_pi'] for fila in reservas_info]
    if (
        orden.estado != Orden.Estado.AUTORIZANDO or len(estados) < 2
        or 'requires_capture' not in estados
        or not any(estado in ('requires_payment_method', 'requires_confirmation',
                             'requires_action', 'processing') for estado in estados)
        or not getattr(settings, 'FRONTEND_URL', '')
        or not (settings.RESEND_API_KEY and settings.RESEND_FROM)
    ):
        return False
    try:
        ahora = timezone.now()
        with scope.con_empresa(orden.empresa_lider):
            reclamado = Orden.objects.filter(pk=orden.pk, retomar_notificado_en__isnull=True).update(
                retomar_notificado_en=ahora,
            )
        if not reclamado:
            return False
        enviado = enviar_correo_retomar_orden(orden)
        if not enviado:
            with scope.con_empresa(orden.empresa_lider):
                Orden.objects.filter(pk=orden.pk, retomar_notificado_en=ahora).update(retomar_notificado_en=None)
        return enviado
    except Exception:
        logger.exception('Fallo al evaluar el aviso de retomar de la orden %s', orden.pk)
        return False


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

        # 3. Aviso a cada empresa que participa (una sola vez por empresa)
        avisos_empresa = []
        avisadas = set()
        prev_alcance = getattr(connection, 'alcance_actual', None)
        connection.alcance_actual = None
        try:
            for r in reservas:
                if r.empresa_id in avisadas:
                    continue
                avisadas.add(r.empresa_id)
                try:
                    with scope.con_empresa(r.empresa):
                        avisos_empresa.append(enviar_aviso_empresa(r))
                except Exception:
                    logger.exception(
                        'Fallo inesperado al avisar a la empresa de la reserva %s de orden %s',
                        r.pk,
                        orden.pk,
                    )
                    avisos_empresa.append(False)
        finally:
            connection.alcance_actual = prev_alcance
            if connection.vendor == 'postgresql' and prev_alcance:
                with connection.cursor() as cursor:
                    if prev_alcance[0] == 'empresa':
                        cursor.execute(f'SET LOCAL app.current_empresa_id = {int(prev_alcance[1])}')
                    elif prev_alcance[0] == 'operador':
                        cursor.execute("SET LOCAL app.operador_plataforma = 'on'")

        return {'email': email_enviado, 'whatsapp': wa_resultados, 'empresas': avisos_empresa}
    except Exception:
        logger.exception('Error no controlado en notificar_orden_pagada para orden %s', getattr(orden, 'pk', None))
        return {'email': False, 'whatsapp': []}


# ---------------------------------------------------------------------------
# Avisos de reembolso por falta de cupo (spec §4.5)
# ---------------------------------------------------------------------------

def enlace_precargado_reserva(reserva, lang='es'):
    """Enlace del sitio con el viaje precargado para que el cliente elija otra fecha."""
    base = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    if reserva.servicio_id and reserva.servicio:
        params = {
            'servicio': reserva.servicio.slug,
            'empresa': reserva.empresa.slug,
            'day': reserva.fecha.isoformat() if reserva.fecha else '',
            'people': reserva.numero_personas or 1,
        }
        if reserva.hora:
            params['time'] = reserva.hora.strftime('%H:%M')
        if reserva.vendedora_id and reserva.vendedora:
            params['ref'] = reserva.vendedora.codigo
        query = urlencode(params)
        return f'{base}/{lang}/reservar?{query}' if base else f'/{lang}/reservar?{query}'
    elif reserva.paquete_id and reserva.paquete:
        sede = getattr(reserva.paquete, 'sede', None)
        sede_slug = sede.slug if sede else (reserva.empresa.sede.slug if reserva.empresa_id and hasattr(reserva.empresa, 'sede') else '')
        params = {
            'paquete': reserva.paquete.slug,
            'sede': sede_slug,
        }
        if reserva.vendedora_id and reserva.vendedora:
            params['ref'] = reserva.vendedora.codigo
        query = urlencode(params)
        return f'{base}/{lang}/reservar?{query}' if base else f'/{lang}/reservar?{query}'
    return ''


def _asunto_reembolso_sin_cupo(reserva):
    return f'No pudimos asegurar tu lugar — {reserva.fecha}'


def _cuerpo_reembolso_sin_cupo_html(reserva):
    monto = f'{reserva.monto_reembolsado or reserva.monto_pagado or 0} {reserva.moneda}'
    enlace = enlace_precargado_reserva(reserva)
    boton = (
        f'<p><a href="{escape(enlace, quote=True)}" style="display:inline-block;padding:10px 20px;background-color:#0284c7;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Elegir otra fecha</a></p>'
        if enlace else ''
    )
    return (
        f'<p>Hola {_html(reserva.nombre_cliente)},</p>'
        f'<p>No pudimos asegurar tu lugar para el {reserva.fecha}. Ya solicitamos el reembolso completo de {monto}; tu banco puede tardar en reflejarlo.</p>'
        f'{boton}'
    )


def enviar_correo_reembolso_sin_cupo(reserva):
    """Correo al cliente via Resend cuando se cancela por falta de cupo."""
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando correo de reembolso sin cupo de la reserva %s', reserva.pk)
        return False

    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [reserva.correo_cliente],
        'subject': _asunto_reembolso_sin_cupo(reserva),
        'html': _cuerpo_reembolso_sin_cupo_html(reserva),
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
    except requests.RequestException as error:
        logger.exception(
            'Fallo el correo de reembolso sin cupo de la reserva %s: %s',
            reserva.pk,
            _motivo_http(error),
        )
        return False
    return True


def _asunto_alerta_reembolso_empresa(reserva, causa='cupo'):
    return f'ALERTA: reserva #{reserva.pk} · {causa} · reembolsada automáticamente · {reserva.nombre_cliente} · {reserva.telefono_cliente}'


def _cuerpo_alerta_reembolso_empresa_html(reserva, causa='cupo', motivo=None):
    monto = f'{reserva.monto_reembolsado or reserva.monto_pagado or 0} {reserva.moneda}'
    motivo_texto = motivo or reserva.motivo_cancelacion or 'Sin cupo'
    return (
        f'<p>ALERTA: reserva #{reserva.pk} · {_html(causa)} · reembolsada automáticamente · {_html(reserva.nombre_cliente)} · {_html(reserva.telefono_cliente)}</p>'
        f'<ul>'
        f'<li><strong>Folio:</strong> #{reserva.pk}</li>'
        f'<li><strong>Causa:</strong> {_html(causa)}</li>'
        f'<li><strong>Motivo:</strong> {_html(motivo_texto)}</li>'
        f'<li><strong>Cliente:</strong> {_html(reserva.nombre_cliente)}</li>'
        f'<li><strong>Telefono:</strong> {_html(reserva.telefono_cliente)}</li>'
        f'<li><strong>Correo:</strong> {_html(reserva.correo_cliente)}</li>'
        f'<li><strong>Fecha original:</strong> {reserva.fecha}</li>'
        f'<li><strong>Monto reembolsado:</strong> {monto}</li>'
        f'</ul>'
    )


def enviar_alerta_reembolso_empresa(reserva, causa='cupo', motivo=None):
    """Aviso a Empresa.correos_aviso de una reserva cancelada con reembolso automatico."""
    destinatarios = reserva.empresa.lista_correos_aviso()
    if not destinatarios:
        return False
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando alerta a la empresa de la reserva %s', reserva.pk)
        return False

    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json={
                'from': settings.RESEND_FROM,
                'to': destinatarios,
                'reply_to': reserva.correo_cliente,
                'subject': _asunto_alerta_reembolso_empresa(reserva, causa=causa),
                'html': _cuerpo_alerta_reembolso_empresa_html(reserva, causa=causa, motivo=motivo),
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.exception(
            'Fallo la alerta a la empresa para reserva %s: %s',
            reserva.pk,
            _motivo_http(error),
        )
        return False
    return True


def enviar_whatsapp_reembolso_sin_cupo(reserva):
    """Aviso de cancelacion/reembolso por WhatsApp Business API.
    Apagado por defecto, solo se envia si WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO esta configurado."""
    template = getattr(settings, 'WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO', '')
    if not template:
        return False
    if not (settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID):
        logger.info('WhatsApp sin configurar, no se mando mensaje de reembolso de la reserva %s', reserva.pk)
        return False

    monto = str(reserva.monto_reembolsado or reserva.monto_pagado or 0)
    parametros = [
        reserva.nombre_cliente,
        str(reserva.fecha),
        monto,
        reserva.moneda,
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
                    'name': template,
                    'language': {'code': getattr(settings, 'WHATSAPP_TEMPLATE_LANG', 'es_MX')},
                    'components': [{
                        'type': 'body',
                        'parameters': [{'type': 'text', 'text': p} for p in parametros],
                    }],
                },
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.exception(
            'Fallo el WhatsApp de reembolso sin cupo de la reserva %s: %s',
            reserva.pk,
            _motivo_http(error),
        )
        return False
    return True


def notificar_reembolso_sin_cupo(reserva, causa='cupo', motivo=None):
    """Notifica reembolso automatico de reserva por falta de cupo u otra razon.
    - causa == 'cupo': correo al cliente y whatsapp (si esta configurado).
    - Para cualquier causa: alerta interna a Empresa.correos_aviso.
    Nunca lanza.
    """
    resultado = {
        'email': False,
        'alerta_empresa': False,
        'whatsapp': False,
    }
    if causa == 'cupo':
        resultado['email'] = enviar_correo_reembolso_sin_cupo(reserva)
        resultado['whatsapp'] = enviar_whatsapp_reembolso_sin_cupo(reserva)

    resultado['alerta_empresa'] = enviar_alerta_reembolso_empresa(reserva, causa=causa, motivo=motivo)
    return resultado


def notificar_reembolso(reserva, causa='cupo', motivo=None):
    return notificar_reembolso_sin_cupo(reserva, causa=causa, motivo=motivo)


enviar_alerta_empresa_reembolso = enviar_alerta_reembolso_empresa


def _asunto_fallo_reembolso(reserva):
    return f'URGENTE: Fallo de reembolso en reserva #{reserva.pk}'


def _cuerpo_fallo_reembolso_html(reserva, monto, motivo=None):
    monto_texto = f'{monto} {reserva.moneda}'
    motivo_texto = motivo or 'Error al procesar el reembolso en Stripe'
    return (
        f'<p><strong>ALERTA URGENTE:</strong> No se pudo procesar el reembolso automático de la reserva #{reserva.pk}.</p>'
        f'<p>El cobro fue recibido pero el reembolso en Stripe falló. La reserva sigue en estado pendiente de pago con dinero cobrado. '
        f'Se requiere intervención manual inmediata para resolver el reembolso.</p>'
        f'<ul>'
        f'<li><strong>Folio:</strong> #{reserva.pk}</li>'
        f'<li><strong>Monto a reembolsar:</strong> {monto_texto}</li>'
        f'<li><strong>Motivo de cancelación:</strong> {_html(motivo_texto)}</li>'
        f'<li><strong>Cliente:</strong> {_html(reserva.nombre_cliente)}</li>'
        f'<li><strong>Teléfono:</strong> {_html(reserva.telefono_cliente)}</li>'
        f'<li><strong>Correo:</strong> {_html(reserva.correo_cliente)}</li>'
        f'<li><strong>PaymentIntent:</strong> {_html(reserva.stripe_payment_intent_id or "N/A")}</li>'
        f'</ul>'
    )


def notificar_fallo_reembolso(reserva, monto, motivo=None):
    """Alerta urgente a Empresa.correos_aviso cuando el reembolso automatico falla.
    Nunca lanza."""
    destinatarios = reserva.empresa.lista_correos_aviso()
    if not destinatarios:
        return False
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando alerta urgente de la reserva %s', reserva.pk)
        return False

    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json={
                'from': settings.RESEND_FROM,
                'to': destinatarios,
                'reply_to': reserva.correo_cliente,
                'subject': _asunto_fallo_reembolso(reserva),
                'html': _cuerpo_fallo_reembolso_html(reserva, monto=monto, motivo=motivo),
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.exception(
            'Fallo la alerta urgente de fallo de reembolso para reserva %s: %s',
            reserva.pk,
            _motivo_http(error),
        )
        return False
    return True


enviar_alerta_fallo_reembolso = notificar_fallo_reembolso


# ---------------------------------------------------------------------------
# Correos de cuenta (recuperacion de contrasena). Reglas propias, mas estrictas que las de reserva:
# nunca llevan `bcc` (RESEND_BCC copiaria el codigo al buzon del negocio), el asunto no lleva el codigo y
# ningun fallo se registra con traza (`logger.exception` / `exc_info` dejaria las variables locales,
# con el codigo, a la vista de Sentry).
# ---------------------------------------------------------------------------

def _post_resend_seguro(cuerpo, etiqueta):
    """POST a Resend para un correo que lleva o anuncia una credencial. True si se envio.

    Registra solo la etiqueta y el codigo HTTP o la clase del error: ni el cuerpo del correo, ni el
    mensaje de la excepcion, ni una traza.
    """
    try:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json=cuerpo,
            timeout=TIMEOUT_SEGUNDOS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        estado = getattr(getattr(error, 'response', None), 'status_code', None)
        logger.warning('Fallo el correo de cuenta "%s" (%s)', etiqueta, estado or type(error).__name__)
        return False
    return True


def _resend_configurado():
    return bool(settings.RESEND_API_KEY and settings.RESEND_FROM)


def _pie_de_cuenta(texto):
    return plantilla.t(escape(texto), 14, 400, plantilla.SUAVE, 1.5)


def _cuerpo_codigo_html(usuario, codigo):
    minutos = settings.RECUPERACION_CODIGO_MINUTOS
    digitos = codigo.revelar() if hasattr(codigo, 'revelar') else str(codigo)
    recuadro = plantilla.titular(
        escape(digitos), 40, plantilla.BLANCO, 'letter-spacing:0.25em;padding-top:12px;'
    )
    return plantilla.correo(
        actividad='cuenta', empresa='Sun Baja Experience', titulo='Tu código', producto='Recuperar contraseña',
        intro_html=f'Usa este código para crear una contraseña nueva. Vence en {minutos} minutos.{recuadro}',
        etiqueta_pares='Tu cuenta', pares=[('Usuario', _html(usuario))],
        siguiente_html=plantilla.parrafo(
            'Escribe el código y tu contraseña nueva en la pantalla de recuperación. '
            'Si no lo pediste, ignóralo: tu contraseña no cambia.'
        ),
        previa=f'Tu código vence en {minutos} minutos.',
        pie_html=_pie_de_cuenta('Nunca compartas este código: nadie del negocio te lo va a pedir.'),
    )


def enviar_correo_codigo_recuperacion(destino, usuario, codigo):
    """Manda el codigo de 6 digitos a la direccion GUARDADA de la cuenta. True si se mando.

    `codigo` llega como `apps.cuentas.seguridad.Secreto` (o texto). Nunca lleva `bcc`.
    """
    if not _resend_configurado():
        logger.info('Resend sin configurar, no se mando el codigo de recuperacion')
        return False

    html_correo = _cuerpo_codigo_html(usuario, codigo)
    cuerpo = {
        'from': settings.RESEND_FROM,
        'to': [destino],
        'subject': 'Tu código para recuperar la contraseña',
        'html': html_correo,
        'text': plantilla.a_texto(html_correo),
    }
    return _post_resend_seguro(cuerpo, 'codigo de recuperacion')


def _cuerpo_cambio_html(usuario, para_el_usuario):
    if para_el_usuario:
        intro = 'Se cambió la contraseña de tu cuenta.'
        siguiente = plantilla.parrafo(
            'Si no fuiste tú, avisa de inmediato a tu jefe: alguien más pudo entrar a tu correo.'
        )
    else:
        intro = 'Se cambió la contraseña de una cuenta del backoffice.'
        siguiente = plantilla.parrafo('Es un aviso: no necesitas hacer nada si fue la persona de la cuenta.')
    return plantilla.correo(
        actividad='cuenta', empresa='Sun Baja Experience', titulo='Contraseña cambiada',
        intro_html=intro, etiqueta_pares='Tu cuenta' if para_el_usuario else 'La cuenta',
        pares=[('Usuario', _html(usuario))], siguiente_html=siguiente, previa=intro,
        pie_html=_pie_de_cuenta('Este aviso no lleva ningún código ni contraseña.'),
    )


def enviar_correo_contrasena_cambiada(destino, usuario, copia_a=()):
    """Avisa a la cuenta que su contrasena cambio; `copia_a` recibe un aviso aparte (sin bcc ni codigo).

    True si el aviso a la cuenta salio; que falle la copia al administrador no cambia ese resultado.
    """
    if not _resend_configurado():
        logger.info('Resend sin configurar, no se mando el aviso de cambio de contrasena')
        return False

    html_usuario = _cuerpo_cambio_html(usuario, para_el_usuario=True)
    enviado = _post_resend_seguro({
        'from': settings.RESEND_FROM, 'to': [destino], 'subject': 'Tu contraseña cambió',
        'html': html_usuario, 'text': plantilla.a_texto(html_usuario),
    }, 'aviso de cambio de contrasena')

    if copia_a:
        html_admin = _cuerpo_cambio_html(usuario, para_el_usuario=False)
        _post_resend_seguro({
            'from': settings.RESEND_FROM, 'to': list(copia_a), 'subject': 'Cambio de contraseña en el backoffice',
            'html': html_admin, 'text': plantilla.a_texto(html_admin),
        }, 'copia del aviso de cambio de contrasena')
    return enviado
