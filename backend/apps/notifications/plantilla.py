"""Membrete de los correos al cliente: la misma cara que la página de confirmación del sitio.

Los clientes de correo no entienden CSS moderno: todo va en tablas con estilos en línea, ancho de 600 px,
fuente del sistema y colores fijos (el fondo arena se declara explícito para que el modo oscuro de Gmail no
lo invierta a medias). Es la misma jerarquía que la confirmación del sitio: una banda del color de la
actividad con la empresa, el folio grande, los datos del viaje como renglones etiqueta/valor, el dinero en
bloques y lo que sigue en un párrafo.

Todo lo que entra aquí como `valor` o `cuerpo` ya viene escapado por quien lo arma (`services._html`):
esta capa no vuelve a escapar para no mostrar `&amp;`, y tampoco escribe datos de personas por su cuenta.
"""
import re
from html import escape, unescape

from apps.fleet.enums import TipoServicio

# Los mismos colores del sitio (globals.css): azul, coral hondo y verde para el campo de color.
BANDA = {'mar': '#1b607f', 'traslado': '#a83226', 'estancia': '#343f04'}
ARENA = '#fcf6ed'
ARENA_CLARA = '#fee0ac'
TINTA = '#1f1a14'
TINTA_SUAVE = '#4a3f33'
BLANCO = '#ffffff'
FUENTE = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def actividad_de(reserva):
    """`mar`, `traslado` o `estancia`: decide el color de la banda."""
    tipo = reserva.servicio.tipo_servicio if reserva.servicio_id else None
    if tipo == TipoServicio.TRANSPORTE:
        return 'traslado'
    if tipo == TipoServicio.HOSPEDAJE:
        return 'estancia'
    return 'mar'


def filas(pares):
    """Renglones etiqueta (izquierda) y valor (derecha). `pares` = [(etiqueta, valor_html)]; los vacíos se omiten."""
    renglones = ''.join(
        f'<tr><td style="padding:10px 0;border-top:1px solid #e8dcc8;font:600 15px {FUENTE};color:{TINTA_SUAVE};">{etiqueta}</td>'
        f'<td align="right" style="padding:10px 0;border-top:1px solid #e8dcc8;font:400 15px {FUENTE};color:{TINTA};">{valor}</td></tr>'
        for etiqueta, valor in pares if valor not in ('', None)
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{renglones}</table>'


def bloque(contenido_html, *, fondo=ARENA_CLARA, color=TINTA):
    """Un recuadro de color para lo que el cliente no debe pasar por alto (el dinero)."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
        f'<tr><td style="background:{fondo};padding:16px 20px;font:400 15px/1.5 {FUENTE};color:{color};">{contenido_html}</td></tr></table>'
    )


def parrafo(contenido_html):
    return f'<p style="margin:16px 0 0;font:400 15px/1.55 {FUENTE};color:{TINTA};">{contenido_html}</p>'


def envolver(*, actividad, empresa, titulo, folio, previa, cuerpo_html, saludo_html=''):
    """El correo completo: banda con la empresa, título y folio grandes, el cuerpo y el pie.

    `previa` es el texto que el cliente ve en la bandeja junto al asunto (se esconde en el cuerpo).
    """
    banda = BANDA.get(actividad, BANDA['mar'])
    folio_html = (
        f'<div style="font:600 13px {FUENTE};letter-spacing:.08em;text-transform:uppercase;color:{TINTA_SUAVE};">Folio</div>'
        f'<div style="font:700 28px {FUENTE};color:{TINTA};">#{escape(str(folio))}</div>'
    ) if folio else ''
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">'
        f'<title>{escape(titulo)}</title></head>'
        f'<body style="margin:0;padding:0;background:{ARENA};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{ARENA};">{escape(previa)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{ARENA};">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">'
        f'<tr><td style="background:{banda};padding:20px 24px;font:600 13px {FUENTE};letter-spacing:.08em;'
        f'text-transform:uppercase;color:{BLANCO};">Sun Baja Experience'
        f'<div style="font:700 22px {FUENTE};letter-spacing:0;text-transform:none;color:{BLANCO};padding-top:4px;">{escape(empresa)}</div></td></tr>'
        f'<tr><td style="background:{BLANCO};padding:28px 24px 8px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font:700 26px/1.15 {FUENTE};color:{TINTA};">{escape(titulo)}</td>'
        f'<td align="right" valign="bottom" style="padding-left:12px;">{folio_html}</td></tr></table>'
        f'{saludo_html}</td></tr>'
        f'<tr><td style="background:{BLANCO};padding:8px 24px 28px;">{cuerpo_html}</td></tr>'
        f'<tr><td style="padding:16px 24px;font:400 13px/1.5 {FUENTE};color:{TINTA_SUAVE};">'
        f'{escape(empresa)} · Sun Baja Experience<br>Guarda este correo: es tu comprobante. '
        f'Si necesitas un cambio, escríbenos por WhatsApp con tu folio.</td></tr>'
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
