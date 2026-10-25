"""La cara de los correos al cliente: la misma de la página de confirmación del sitio.

El dueño pidió (2026-10-24) que los correos sigan el estilo visual de la confirmación de reserva del sitio, no uno
inventado aparte. Es el mismo orden y la misma voz: un campo de color de la actividad con el titular grande en la
letra de los titulares del sitio (mayúsculas, negrita, monoespaciada: es la regla de marca del dueño, no de la
skill de taste, y por eso se conserva), el folio a la derecha, el saludo y el producto; debajo, sobre arena, «Lo que
reservaste» (etiqueta a la izquierda, valor a la derecha), «El dinero» (el bloque tinta de «Pagaste hoy» y el bloque
arena-clara del resto), «Qué sigue» y «Si algo cambia» (la cifra grande y su texto).

Los clientes de correo no cargan la fuente del sitio (Consola Mono): se usa Consolas / Courier New. No hay imágenes (se
ve completo con las imágenes bloqueadas). Tablas con estilos en línea, 600 px, `color-scheme: light only`.

Todo lo que entra como `valor` o `*_html` ya viene escapado por quien lo arma (`services._html`): esta capa no vuelve a
escapar para no mostrar `&amp;`, y tampoco escribe datos de personas por su cuenta.
"""
import re
from datetime import datetime, timedelta
from html import escape, unescape

from apps.fleet.enums import TipoServicio

# Los campos de color del sitio: azul (mar), coral hondo (traslado) y verde (estancia).
CAMPO = {'mar': '#1b607f', 'traslado': '#a83226', 'estancia': '#343f04'}
ARENA = '#fcf6ed'
ARENA_CLARA = '#fee0ac'
TINTA = '#1f1a14'
SUAVE = '#4a3f33'
BLANCO = '#ffffff'
BLANCO_SUAVE = '#e9eff2'
CUERPO = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
TITULAR = "Consolas, 'Lucida Console', 'Courier New', monospace"

DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre')

# Las garantías de la confirmación del sitio (sedeContenido.tranquilidad): mismos textos, mismas cifras.
GARANTIAS = (
    ('100 %', 'Si hay mal clima', 'Si el mal clima impide salir, hay reembolso completo.'),
    ('48 h', 'Cambio de fecha', 'Puedes cambiar la fecha con al menos 48 horas de anticipación.'),
)


def actividad_de(reserva):
    """`mar`, `traslado` o `estancia`: decide el campo de color."""
    tipo = reserva.servicio.tipo_servicio if reserva.servicio_id else None
    if tipo == TipoServicio.TRANSPORTE:
        return 'traslado'
    if tipo == TipoServicio.HOSPEDAJE:
        return 'estancia'
    return 'mar'


def dia_largo(fecha):
    """«Lunes 7 de diciembre»."""
    return f'{DIAS[fecha.weekday()].capitalize()} {fecha.day} de {MESES[fecha.month - 1]}'


def hora_12(hora):
    """«6:00 a. m.» a partir de un `time`."""
    sufijo = 'a. m.' if hora.hour < 12 else 'p. m.'
    return f'{hora.hour % 12 or 12}:{hora.minute:02d} {sufijo}'


def quince_antes(hora):
    """La hora de llegada: 15 minutos antes de la salida (la regla que ya decía el correo de asignación)."""
    return (datetime.combine(datetime(2000, 1, 1), hora) - timedelta(minutes=15)).time()


def t(texto, tam, peso=400, color=TINTA, interlin=1.3, extra='', familia=CUERPO):
    return f'<div style="font:{peso} {tam}px/{interlin} {familia};color:{color};{extra}">{texto}</div>'


def titular(texto, tam, color=TINTA, extra=''):
    """La letra de los titulares del sitio: mayúsculas, negrita, monoespaciada, apretada."""
    return t(escape(texto.upper()), tam, 700, color, 0.95, f'letter-spacing:-0.03em;{extra}', TITULAR)


def parrafo(contenido_html, color=TINTA, tam=16):
    return t(contenido_html, tam, 400, color, 1.5, 'padding-top:12px;')


def seccion(titulo, contenido_html):
    """Un bloque del cuerpo: su título (letra de titulares) y lo suyo."""
    return (
        f'<tr><td class="pad" style="background:{ARENA};padding:28px 32px 0;">{titular(titulo, 24)}'
        f'<div style="padding-top:16px;">{contenido_html}</div></td></tr>'
    )


def filas(pares):
    """«Lo que reservaste»: etiqueta en negrita a la izquierda y valor a la derecha, como en el sitio."""
    cuerpo = ''.join(
        f'<tr><td valign="top" style="padding:6px 16px 6px 0;font:600 16px/1.5 {CUERPO};color:{TINTA};">{e}</td>'
        f'<td valign="top" align="right" style="padding:6px 0;font:400 16px/1.5 {CUERPO};color:{TINTA};">{v}</td></tr>'
        for e, v in pares if v not in ('', None) and e
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cuerpo}</table>' if cuerpo else ''


def bloque(contenido_html, fondo, color):
    """Un renglón de color del dinero («Pagaste hoy», «Resto en efectivo»)."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;"><tr>'
        f'<td style="background:{fondo};padding:16px 20px;font:400 16px/1.45 {CUERPO};color:{color};">{contenido_html}</td></tr></table>'
    )


def bloque_pagado(monto_html):
    """El bloque tinta de «Pagaste hoy»."""
    return bloque(
        t('Pagaste hoy', 16, 600, BLANCO, 1.2) + titular(monto_html, 24, BLANCO, 'padding-top:6px;'), TINTA, BLANCO,
    )


def bloque_resto(frase_html):
    """El bloque arena-clara de lo que queda en efectivo."""
    return bloque(t(frase_html, 17, 600, TINTA, 1.45), ARENA_CLARA, TINTA)


def recuadro(contenido_html):
    """Un aviso que el cliente no debe pasar por alto, en el campo arena-clara."""
    return bloque(contenido_html, ARENA_CLARA, TINTA)


def garantias():
    filas_ = ''.join(
        f'<tr><td width="88" valign="top" style="padding:8px 0;">{titular(cifra, 24)}</td>'
        f'<td valign="top" style="padding:8px 0;">{t(escape(titulo), 16, 600, TINTA, 1.2)}'
        f'{t(escape(texto), 16, 400, TINTA, 1.5, "padding-top:4px;")}</td></tr>'
        for cifra, titulo, texto in GARANTIAS
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas_}</table>'


def correo(*, actividad, empresa, titulo, folio='', producto='', intro_html='', pares=(), dinero_html='',
           siguiente_html='', con_garantias=False, previa='', etiqueta_pares='Lo que reservaste'):
    """El correo completo, con el orden de la página de confirmación del sitio.

    `titulo` es el titular grande; `producto` la línea en negrita bajo el saludo (servicio y empresa).
    """
    campo = CAMPO.get(actividad, CAMPO['mar'])
    folio_html = (
        f'<td class="col" valign="top" align="right" style="padding-left:16px;">'
        f'{t("Folio", 16, 600, BLANCO_SUAVE, 1.2)}{titular("#" + str(folio), 40, BLANCO)}</td>'
    ) if folio else ''
    linea_producto = t(
        f'{escape(producto)}<span style="font-weight:400;"> · {escape(empresa)}</span>' if producto else escape(empresa),
        20, 700, BLANCO, 1.3, 'padding-top:22px;',
    )
    secciones = ''
    if pares:
        secciones += seccion(etiqueta_pares, filas(pares))
    if dinero_html:
        secciones += seccion('El dinero', dinero_html)
    if siguiente_html:
        secciones += seccion('Qué sigue', siguiente_html)
    if con_garantias:
        secciones += seccion('Si algo cambia', garantias())
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">'
        '<style>@media (max-width:480px){.col{display:block!important;width:100%!important;text-align:left!important;'
        'padding-left:0!important;padding-top:14px!important}.pad{padding-left:20px!important;padding-right:20px!important}}</style>'
        f'<title>{escape(titulo)}</title></head>'
        f'<body style="margin:0;padding:0;background:{ARENA};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{ARENA};">{escape(previa)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{ARENA};">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">'
        f'<tr><td class="pad" style="background:{campo};padding:36px 32px 32px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td class="col" valign="top">{titular(titulo, 40, BLANCO)}</td>{folio_html}</tr></table>'
        f'{t(intro_html, 20, 400, BLANCO_SUAVE, 1.35, "padding-top:22px;") if intro_html else ""}'
        f'{linea_producto}</td></tr>'
        f'{secciones}'
        f'<tr><td class="pad" style="background:{ARENA};padding:32px 32px 36px;">'
        f'{t("Guarda este correo: es tu comprobante. Si necesitas un cambio, escríbenos por WhatsApp con tu folio.", 14, 400, SUAVE, 1.5)}'
        f'{t(escape(empresa) + " · Sun Baja Experience", 14, 400, SUAVE, 1.5, "padding-top:6px;")}</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def a_texto(html):
    """La versión de texto plano del mismo correo, en el mismo orden."""
    texto = re.sub(r'(?is)<(head|style|script)[^>]*>.*?</\1>', '', html)
    texto = re.sub(r'(?i)</(tr|p|div|h1|h2|li|table)>|<br\s*/?>', '\n', texto)
    texto = re.sub(r'(?i)</td>', '  ', texto)
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = unescape(texto)
    lineas = [re.sub(r'[ \t]+', ' ', linea).strip() for linea in texto.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lineas)).strip() + '\n'
