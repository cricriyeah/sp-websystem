"""Pantalla de solo lectura `/admin/calendario/` (ver `config/urls.py`).

Va montada dentro del admin como el panel de finanzas: hereda su sesion, su menu y su
login. Aqui solo se arma el estado de la pantalla (vista, periodo, empresa, canceladas
—todo en la URL, asi Atras y los enlaces funcionan) y la geometria de Dia, Semana y
Mes; lo que hay en cada dia lo decide `calendario.py`.

Un parametro roto o inventado cae en su valor por defecto: es una pantalla de consulta
y una URL mal pegada no tiene por que devolver un error.
"""
from calendar import monthrange
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import reverse
from django.utils import formats, timezone

from apps.tenancy import scope
from apps.tenancy.models import Empresa

from .calendario import DIA_DE_MAR, MAR, TRASLADO, armar_calendario, tira_de_pangas

VISTAS = [('dia', 'Día'), ('semana', 'Semana'), ('mes', 'Mes')]
VISTA_DEFAULT = 'semana'

# Mas de 6 eventos en un dia de la semana se acortan a 5 + "+N mas" (que lleva al dia).
MAXIMO_EVENTOS_SEMANA = 6
EVENTOS_VISIBLES_SEMANA = 5
# En el mes, la celda ensena dos renglones de texto y a lo mucho dos barras de estancia.
LINEAS_MES = 2
CARRILES_MES = 2

VACIO = {'dia': 'este día', 'semana': 'esta semana', 'mes': 'este mes'}

LEYENDA = [
    ('sin_panga', 'Sin panga'),
    ('atrasada', 'Atrasada'),
    ('asignada', 'Asignada'),
    ('completada', 'Completada'),
    ('cancelada', 'Cancelada'),
]


def _fecha(valor, defecto):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return defecto


def _lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _primero_del_mes(fecha):
    return fecha.replace(day=1)


def _ultimo_del_mes(fecha):
    return fecha.replace(day=monthrange(fecha.year, fecha.month)[1])


def _ancla_y_rango(vista, pedida):
    """`(ancla, desde, hasta)`: el ancla normalizada y el rango que se dibuja, inclusive.

    La semana empieza en lunes. El mes dibuja semanas completas (de lunes a domingo), asi
    que su rango incluye dias grises de los meses vecinos.
    """
    if vista == 'dia':
        return pedida, pedida, pedida
    if vista == 'semana':
        lunes = _lunes(pedida)
        return lunes, lunes, lunes + timedelta(days=6)
    primero, ultimo = _primero_del_mes(pedida), _ultimo_del_mes(pedida)
    return primero, _lunes(primero), ultimo + timedelta(days=6 - ultimo.weekday())


def _vecino(vista, ancla, salto):
    """El ancla del periodo anterior (-1) o siguiente (+1)."""
    if vista == 'dia':
        return ancla + timedelta(days=salto)
    if vista == 'semana':
        return ancla + timedelta(days=7 * salto)
    mes = ancla.month + salto
    return date(ancla.year + (mes - 1) // 12, (mes - 1) % 12 + 1, 1)


def _fmt(fecha, formato):
    return formats.date_format(fecha, formato)


def _etiqueta(vista, d1, d2):
    """El periodo en la fila de controles: «19 – 25 oct 2026»."""
    if vista == 'dia':
        return _fmt(d1, 'D j M Y')
    if vista == 'mes':
        return _fmt(d1, 'F Y')
    if d1.year != d2.year:
        return f"{_fmt(d1, 'j M Y')} – {_fmt(d2, 'j M Y')}"
    if d1.month != d2.month:
        return f"{_fmt(d1, 'j M')} – {_fmt(d2, 'j M Y')}"
    return f"{d1.day} – {_fmt(d2, 'j M Y')}"


def _frase(vista, d1, d2):
    """El periodo dentro de una oracion: «del 19 al 25 de octubre»."""
    if vista == 'dia':
        return 'el ' + _fmt(d1, r'l j \d\e F')
    if vista == 'mes':
        return 'en ' + _fmt(d1, r'F \d\e Y')
    if d1.year != d2.year:
        return f"del {_fmt(d1, r'j \d\e F \d\e Y')} al {_fmt(d2, r'j \d\e F \d\e Y')}"
    if d1.month != d2.month:
        return f"del {_fmt(d1, r'j \d\e F')} al {_fmt(d2, r'j \d\e F')}"
    return f"del {d1.day} al {_fmt(d2, r'j \d\e F')}"


def _barras(lunes, estancias):
    """Las estancias que tocan la semana de `lunes`, con su columna, su largo y su carril.

    Una barra que empieza antes del lunes o sigue despues del domingo lleva el borde recto
    de ese lado. Los carriles se asignan de arriba abajo: la primera fila donde cabe.
    """
    domingo = lunes + timedelta(days=6)
    barras = []
    for estancia in estancias:
        if estancia.inicio > domingo or estancia.ultimo_dia < lunes:
            continue
        primero, ultimo = max(estancia.inicio, lunes), min(estancia.ultimo_dia, domingo)
        barras.append({
            'estancia': estancia,
            'col': (primero - lunes).days + 1,
            'span': (ultimo - primero).days + 1,
            'continua_antes': estancia.inicio < lunes,
            'continua_despues': estancia.ultimo_dia > domingo,
        })
    barras.sort(key=lambda b: (b['col'], -b['span'], b['estancia'].reserva.pk))
    ocupado_hasta = []  # por carril, la ultima columna que ocupa
    for barra in barras:
        ultima = barra['col'] + barra['span'] - 1
        for i, hasta in enumerate(ocupado_hasta):
            if hasta < barra['col']:
                ocupado_hasta[i], barra['carril'] = ultima, i + 1
                break
        else:
            ocupado_hasta.append(ultima)
            barra['carril'] = len(ocupado_hasta)
    return barras


def _pct(tira):
    return min(100, round(100 * tira.ocupadas / tira.capacidad)) if tira and tira.capacidad else 0


class _Contexto:
    """Lo que comparten las tres vistas al armar un dia."""

    def __init__(self, request, hoy, tiras, mostrar_empresa, empresa_param):
        self.request = request
        self.hoy = hoy
        self.tiras = tiras
        self.mostrar_empresa = mostrar_empresa
        self.empresa_param = empresa_param

    def url(self, vista, desde=None, canceladas=None):
        params = {'vista': vista}
        if desde:
            params['desde'] = desde.isoformat()
        if self.empresa_param:
            params['empresa'] = self.empresa_param
        if canceladas is None:
            canceladas = self.request.GET.get('canceladas') == '1'
        if canceladas:
            params['canceladas'] = '1'
        return f'{self.request.path}?{urlencode(params)}'

    def dia(self, fecha):
        """Lo comun de un dia: su enlace a la vista Dia y su tira de pangas."""
        tira = self.tiras.get(fecha) if self.tiras else None
        return {
            'fecha': fecha,
            'es_hoy': fecha == self.hoy,
            'fin_de_semana': fecha.weekday() >= 5,
            'url_dia': self.url('dia', fecha),
            'tira': tira,
            'tira_pct': _pct(tira),
            # "Lleno" solo importa de hoy en adelante; un dia que ya paso no admite nada.
            'lleno': bool(tira and tira.lleno and fecha >= self.hoy),
            'cerrado': bool(tira and tira.cerrado and fecha >= self.hoy),
        }


def _semana(ctx, lunes, cal):
    eventos = {}
    for evento in cal.eventos:
        eventos.setdefault(evento.fecha, []).append(evento)
    dias = []
    for i in range(7):
        dia = ctx.dia(lunes + timedelta(days=i))
        del_dia = eventos.get(dia['fecha'], [])
        corto = len(del_dia) > MAXIMO_EVENTOS_SEMANA
        dia.update(
            col=i + 1,
            eventos=del_dia[:EVENTOS_VISIBLES_SEMANA] if corto else del_dia,
            n_mas=len(del_dia) - EVENTOS_VISIBLES_SEMANA if corto else 0,
        )
        dias.append(dia)
    barras = _barras(lunes, cal.estancias)
    carriles = max((b['carril'] for b in barras), default=0)
    return {
        'dias': dias,
        'barras': barras,
        'carriles': carriles,
        # Cabecera, un carril por barra y, al fondo, los eventos del dia.
        'filas': ' '.join(['auto', *['26px'] * carriles, 'minmax(7rem, auto)']),
        'fila_eventos': carriles + 2,
    }


def _mes(ctx, desde, hasta, primero_del_mes, cal):
    eventos = {}
    for evento in cal.eventos:
        eventos.setdefault(evento.fecha, []).append(evento)
    semanas = []
    lunes = desde
    while lunes <= hasta:
        barras = _barras(lunes, cal.estancias)
        # Las barras que no caben en los dos carriles pasan al "+N mas" de sus dias.
        ocultas = [0] * 7
        for barra in barras:
            if barra['carril'] > CARRILES_MES:
                for col in range(barra['col'] - 1, barra['col'] - 1 + barra['span']):
                    ocultas[col] += 1
        dias = []
        for i in range(7):
            dia = ctx.dia(lunes + timedelta(days=i))
            del_dia = eventos.get(dia['fecha'], [])
            dia.update(
                col=i + 1,
                otro_mes=dia['fecha'].month != primero_del_mes.month,
                lineas=del_dia[:LINEAS_MES],
                n_mas=max(0, len(del_dia) - LINEAS_MES) + ocultas[i],
            )
            dias.append(dia)
        semanas.append({
            'dias': dias,
            'barras': [b for b in barras if b['carril'] <= CARRILES_MES],
        })
        lunes += timedelta(days=7)
    return {'semanas': semanas}


def _dia(ctx, fecha, cal):
    return {
        **ctx.dia(fecha),
        'mar': [e for e in cal.eventos if e.tipo in (MAR, DIA_DE_MAR)],
        'estancias': cal.estancias,
        'traslados': [e for e in cal.eventos if e.tipo == TRASLADO],
    }


def calendario(request):
    """Reservas por dia, semana o mes, con su estado y el detalle al hacer clic.

    Permiso: ver reservas (vendedora, jefe y operador). Cada quien ve su empresa; el
    operador de plataforma elige una —abre en la primera por nombre— o todas juntas.
    """
    if not request.user.has_perm('bookings.view_reserva'):
        raise PermissionDenied

    hoy = timezone.localdate()
    vista = request.GET.get('vista')
    if vista not in dict(VISTAS):
        vista = VISTA_DEFAULT
    pedida = _fecha(request.GET.get('desde'), hoy)
    canceladas = request.GET.get('canceladas') == '1'

    es_operador = scope.es_operador_plataforma(request.user)
    empresas, empresa_param = [], None
    if es_operador:
        empresas = list(Empresa.objects.filter(activo=True).order_by('nombre'))
        por_slug = {e.slug: e for e in empresas}
        elegida = request.GET.get('empresa')
        if elegida == 'todas' or not empresas:
            empresa, empresa_param = None, 'todas'
        else:
            empresa = por_slug.get(elegida, empresas[0])
            empresa_param = empresa.slug
    else:
        empresa = scope.empresa_actual(request)
        if empresa is None:
            raise PermissionDenied

    ancla, desde, hasta = _ancla_y_rango(vista, pedida)
    # "Este mes" no cuenta los dias grises de los meses vecinos que dibuja la rejilla.
    hallazgo_de = (ancla, _ultimo_del_mes(ancla)) if vista == 'mes' else (desde, hasta)

    cal = armar_calendario(
        desde, hasta, empresa, canceladas=canceladas, dias_de_mar=vista == 'dia', hoy=hoy,
        hallazgo_de=hallazgo_de,
    )
    # La tira de pangas es de una flota: con «Todas» no se pinta.
    tiras = tira_de_pangas(desde, hasta, empresa) if empresa is not None else None
    ctx = _Contexto(request, hoy, tiras, mostrar_empresa=es_operador and empresa is None, empresa_param=empresa_param)

    contexto = {
        **admin.site.each_context(request),
        'title': 'Calendario',
        'vista': vista,
        'vistas': [
            {'clave': clave, 'nombre': nombre, 'activa': clave == vista, 'url': ctx.url(clave, pedida)}
            for clave, nombre in VISTAS
        ],
        'ancla': ancla,
        'desde': desde,
        'hasta': hasta,
        'periodo_etiqueta': _etiqueta(vista, *(hallazgo_de if vista == 'mes' else (desde, hasta))),
        'anterior_url': ctx.url(vista, _vecino(vista, ancla, -1)),
        'siguiente_url': ctx.url(vista, _vecino(vista, ancla, 1)),
        'hoy_url': ctx.url(vista),
        'es_operador': es_operador,
        'empresa': empresa,
        'empresas': empresas,
        'empresa_param': empresa_param,
        'mostrar_empresa': ctx.mostrar_empresa,
        'canceladas': canceladas,
        'canceladas_url': ctx.url(vista, ancla, canceladas=not canceladas),
        'hallazgo': cal.hallazgo,
        'frase_periodo': _frase(vista, *hallazgo_de),
        'vacio': not (cal.eventos or cal.estancias),
        'vacio_texto': VACIO[vista],
        'leyenda': [
            {'estilo': estilo, 'nombre': nombre}
            for estilo, nombre in LEYENDA
            if any(p.estilo == estilo for p in (*cal.eventos, *cal.estancias))
        ],
    }

    agenda = reverse('admin:bookings_agenda_changelist')
    periodo = {'periodo': f'{hallazgo_de[0].isoformat()}_{hallazgo_de[1].isoformat()}'}
    if es_operador and empresa is not None:
        periodo['empresa'] = empresa.slug
    contexto['sin_panga_url'] = f'{agenda}?{urlencode(periodo)}'
    contexto['atrasadas_url'] = f'{agenda}?{urlencode({**periodo, "cuando": "atrasadas"})}'

    if vista == 'semana':
        contexto['semana'] = _semana(ctx, desde, cal)
    elif vista == 'mes':
        contexto['mes'] = _mes(ctx, desde, hasta, ancla, cal)
    else:
        contexto['dia'] = _dia(ctx, desde, cal)
    return render(request, 'bookings/calendario.html', contexto)
