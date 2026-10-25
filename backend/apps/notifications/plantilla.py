"""El boleto: la cara de los correos al cliente (dirección «El boleto», elegida por el dueño el 2026-10-24).

La idea sale del negocio: una salida de pesca es de madrugada, con una hora que manda (6:00) y un folio que se
muestra en el muelle. El correo es ese boleto: un papel arena sobre el campo de color de la actividad, la hora
enorme, los datos del viaje con el valor por delante de la etiqueta, una fila de puntos como perforación y,
debajo, el talón oscuro con el folio y el dinero.

Reglas de la casa (taste): sin líneas finas, sin degradados, sin sombras, sin mayúsculas diminutas ni
monoespaciada; esquinas rectas o círculos; una sola familia (la del sistema) porque los clientes de correo no
cargan fuentes. Tablas con estilos en línea (Outlook no entiende más) y `color-scheme: light only`. Sin imágenes:
el boleto se ve completo con las imágenes bloqueadas y en Outlook de escritorio.

Todo lo que entra como `valor` o `*_html` ya viene escapado por quien lo arma (`services._html`): esta capa no
vuelve a escapar para no mostrar `&amp;`, y tampoco escribe datos de personas por su cuenta.
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
FUENTE = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre')


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


def t(texto, tam, peso=400, color=TINTA, interlin=1.2, extra=''):
    return f'<div style="font:{peso} {tam}px/{interlin} {FUENTE};color:{color};{extra}">{texto}</div>'


def parrafo(contenido_html, color=TINTA, tam=17):
    return t(contenido_html, tam, 400, color, 1.5, 'padding-top:14px;')


def dato(etiqueta, valor):
    """Una pareja etiqueta/valor sin líneas ni mayúsculas: el valor manda."""
    return f'<tr><td style="padding:14px 0 0;">{t(etiqueta, 16, 600, SUAVE)}{t(valor, 22, 700, TINTA, 1.25)}</td></tr>'


def datos(pares):
    """Los datos del viaje. `pares` = [(etiqueta, valor_html)]; los vacíos se omiten."""
    filas = ''.join(dato(e, v) for e, v in pares if v not in ('', None))
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas}</table>' if filas else ''


def recuadro(contenido_html, fondo=ARENA_CLARA, color=TINTA):
    """Lo que el cliente no debe pasar por alto, en un campo de color."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;"><tr>'
        f'<td style="background:{fondo};padding:18px 22px;font:400 17px/1.45 {FUENTE};color:{color};">{contenido_html}</td></tr></table>'
    )


def perforacion(campo):
    """Fila de puntos redondos del color del campo: la perforación entre el boleto y el talón."""
    punto = (f'<td style="width:10px;"><div style="width:10px;height:10px;border-radius:5px;background:{campo};'
             f'line-height:10px;font-size:1px;">&nbsp;</div></td><td style="width:14px;"></td>')
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{ARENA};">'
        f'<tr><td align="center" style="padding:6px 0;"><table role="presentation" cellpadding="0" cellspacing="0">'
        f'<tr>{punto * 24}</tr></table></td></tr></table>'
    )


def boleto(*, actividad, empresa, linea1, linea2='', intro_html='', pares=(), folio='', talon_html='',
           cierre_html='', previa='', titulo_documento='Reserva confirmada'):
    """El correo completo.

    `linea1` es el día (o el título), `linea2` la hora enorme (puede ir vacía); `pares` los datos; el talón lleva el
    folio a la izquierda y `talon_html` (el dinero) a la derecha; `cierre_html` es lo que sigue.
    """
    campo = CAMPO.get(actividad, CAMPO['mar'])
    grande = t(escape(linea2), 84, 800, campo, 1.0, 'letter-spacing:-2px;') if linea2 else ''
    talon_folio = (
        f'<td class="col" valign="top">{t("Folio", 17, 600, ARENA_CLARA)}{t("#" + escape(str(folio)), 52, 800, ARENA, 1.0)}</td>'
    ) if folio else ''
    talon_der = (
        f'<td class="col" valign="top" align="right" style="padding-top:2px;">{talon_html}</td>'
    ) if talon_html else ''
    talon = (
        f'<tr><td>{perforacion(campo)}</td></tr>'
        f'<tr><td class="pad" style="background:{TINTA};padding:24px 32px;"><table role="presentation" width="100%" '
        f'cellpadding="0" cellspacing="0"><tr>{talon_folio}{talon_der}</tr></table></td></tr>'
    ) if (talon_folio or talon_der) else ''
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">'
        '<style>@media (max-width:480px){.col{display:block!important;width:100%!important;text-align:left!important}'
        '.pad{padding-left:20px!important;padding-right:20px!important}}</style>'
        f'<title>{escape(titulo_documento)}</title></head>'
        f'<body style="margin:0;padding:0;background:{campo};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{campo};">{escape(previa)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{campo};">'
        '<tr><td align="center" style="padding:28px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">'
        f'<tr><td class="pad" style="background:{ARENA};padding:30px 32px 6px;">{t(escape(empresa), 20, 800, campo)}'
        f'{t(escape(linea1), 30, 800, TINTA, 1.1, "padding-top:26px;")}{grande}{intro_html}</td></tr>'
        f'<tr><td class="pad" style="background:{ARENA};padding:8px 32px 26px;">{datos(pares)}</td></tr>'
        f'{talon}'
        f'<tr><td class="pad" style="background:{ARENA};padding:8px 32px 30px;">{cierre_html}</td></tr>'
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
