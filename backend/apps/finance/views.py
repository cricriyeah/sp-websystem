"""Panel de dinero. Solo jefes.

Va montado dentro del admin (`/admin/finanzas/`, ver `config/urls.py`) para
heredar su sesion, su menu y su login — no es una app aparte con su propia
autenticacion.
"""
import json
from calendar import monthrange
from datetime import date, timedelta

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import formats

from apps.tenancy import scope
from apps.tenancy.permisos_unfold import puede_ver_finanzas

from .services import (
    balances,
    balances_por_dia,
    movimientos,
    resumen,
    totales_de_movimientos,
)


# Lo que ofrece el select, en el orden en que se ve. La clave es lo que viaja en
# la URL (`?periodo=mes`) y no las fechas, para que un link guardado siga
# significando lo mismo la semana que entra.
PERIODOS = [
    ('hoy', 'Hoy'),
    ('semana', 'Esta semana'),
    ('mes', 'Este mes'),
    ('mes_pasado', 'Mes pasado'),
    ('ano', 'Este ano'),
]

PERIODO_DEFAULT = 'mes'


def rango_del_periodo(periodo, hoy):
    """Las dos fechas que significa una opcion del select, inclusivas.

    Los periodos en curso terminan hoy y no al final del calendario: nadie quiere
    ver en el historico dias que todavia no pasan. `mes_pasado` si va completo,
    porque ya termino.

    Una clave que no existe cae en el mes actual, igual que hace `_mes_pedido` con
    un `?mes=` roto: es una pantalla de consulta y una URL mal pegada no tiene por
    que devolver un error.
    """
    if periodo == 'hoy':
        return hoy, hoy
    if periodo == 'semana':
        # Lunes de esta semana. weekday(): lunes es 0.
        return hoy - timedelta(days=hoy.weekday()), hoy
    if periodo == 'mes_pasado':
        ultimo = hoy.replace(day=1) - timedelta(days=1)
        return ultimo.replace(day=1), ultimo
    if periodo == 'ano':
        return hoy.replace(month=1, day=1), hoy
    return hoy.replace(day=1), hoy


def _grafica_de_entradas(desde, hasta, empresa=None):
    """`{moneda: json}` con la serie de entradas por dia, lista para Chart.js.

    El JSON va tal cual al `data-value` del canvas: el `app.js` de Unfold recorre
    los `.chart` de la pagina, lo parsea y instancia Chart.js solo. No hace falta
    escribir JavaScript, y la libreria ya viene con el tema — no se instala nada.

    Se incluyen los dias sin movimiento a proposito. El historico de abajo si los
    omite —ahi cada renglon es un dato y una fila vacia es ruido—, pero en una
    grafica el hueco *es* el dato: se ve de un golpe que ese dia no entro nada.

    Cada moneda va por separado y nunca se suman: el sistema no guarda tipo de
    cambio, asi que un total mezclado seria un numero inventado. Una moneda sin un
    solo movimiento en el periodo no aparece, para no dibujar una grafica plana de
    dolares en un mes que solo cobro en pesos.

    El color se manda como variable CSS y no como valor fijo: Unfold la resuelve
    contra el tema, asi la grafica sigue el modo oscuro y el color primario que se
    configure en el admin.
    """
    entradas_por_dia = {
        dia: {moneda: saldo.entradas for moneda, saldo in por_moneda.items()}
        for dia, por_moneda in balances_por_dia(desde, hasta, empresa=empresa)
    }

    monedas = {
        moneda
        for por_moneda in entradas_por_dia.values()
        for moneda, entradas in por_moneda.items()
        if entradas
    }

    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]

    return {
        moneda: json.dumps({
            'labels': [formats.date_format(dia, 'j M') for dia in dias],
            'datasets': [{
                'label': f'Entradas ({moneda})',
                'data': [
                    float(entradas_por_dia.get(dia, {}).get(moneda, 0)) for dia in dias
                ],
                'backgroundColor': 'var(--color-primary-500)',
                # Unfold trae `maxBarThickness: 4` en sus opciones por defecto,
                # que va bien en sus graficas de tarjeta —son sparklines— y deja
                # rayitas ilegibles en una grafica mensual a todo lo ancho. Se
                # corrige aqui, en el dataset, y no mandando `options` propias: su
                # app.js **reemplaza** sus opciones enteras si se le pasan, y ahi
                # se irian la rejilla punteada, los colores del tema y el tooltip.
                'maxBarThickness': 40,
                'barPercentage': 0.9,
                'categoryPercentage': 0.9,
                'borderRadius': 3,
            }],
        })
        for moneda in sorted(monedas)
    }


def _mes_pedido(request, hoy):
    """El mes que se esta viendo en el historico, de `?mes=YYYY-MM`.

    Un parametro roto o inventado cae en el mes actual: es una pantalla de
    consulta, no tiene por que devolver un error por una URL mal pegada.
    """
    try:
        anio, mes = request.GET['mes'].split('-')
        return date(int(anio), int(mes), 1)
    except (KeyError, ValueError):
        return hoy.replace(day=1)


def _mes_vecino(primero, salto):
    """El primer dia del mes anterior (-1) o del siguiente (+1)."""
    mes = primero.month + salto
    anio = primero.year + (mes - 1) // 12
    return date(anio, (mes - 1) % 12 + 1, 1)


def panel_financiero(request):
    """Tarjeta, efectivo, transferencia, salidas y balance por periodo.

    El operador de plataforma ve todas las Empresas juntas; un jefe ve solo
    la suya. Solo jefes y operadores de plataforma tienen acceso (las vendedoras
    u otros usuarios con membresía reciben 403).
    """
    if not puede_ver_finanzas(request):
        raise PermissionDenied

    operador = scope.es_operador_plataforma(request.user)
    empresa = None if operador else scope.empresa_actual(request)

    hoy = date.today()
    periodo = request.GET.get('periodo', PERIODO_DEFAULT)
    if periodo not in dict(PERIODOS):
        periodo = PERIODO_DEFAULT
    desde, hasta = rango_del_periodo(periodo, hoy)

    mes = _mes_pedido(request, hoy)
    ultimo_dia = mes.replace(day=monthrange(mes.year, mes.month)[1])
    siguiente = _mes_vecino(mes, 1)

    datos_resumen = resumen(hoy, empresa=empresa)

    return render(request, 'finance/panel.html', {
        **admin.site.each_context(request),
        'title': 'Finanzas',
        'acumulado': datos_resumen['acumulado'],
        # El periodo elegido en el select: filtra el balance de arriba y la
        # grafica. El historico de abajo sigue siendo mes a mes con sus flechas,
        # que es lo unico que deja llegar a un mes viejo cualquiera.
        'periodos': PERIODOS,
        'periodo': periodo,
        'periodo_etiqueta': dict(PERIODOS)[periodo],
        'periodo_desde': desde,
        'periodo_hasta': hasta,
        'saldo_periodo': balances(desde, hasta, empresa=empresa),
        'grafica': _grafica_de_entradas(desde, hasta, empresa=empresa),
        'mes_visto': mes,
        'mes_anterior': _mes_vecino(mes, -1),
        # Sin boton para adelantarse a meses que todavia no pasan.
        'mes_siguiente': siguiente if siguiente <= hoy.replace(day=1) else None,
        'dias': balances_por_dia(mes, ultimo_dia, empresa=empresa),
    })


CONCEPTOS_MOVIMIENTOS = {
    'todos': 'Todos los conceptos',
    'stripe': 'En la cuenta (Stripe)',
    'tarjeta': 'Tarjeta',
    'efectivo': 'Efectivo',
    'transferencia': 'Transferencia',
    'reembolsos': 'Reembolsos',
    'contracargos': 'Contracargos perdidos',
}

ETIQUETAS_TOTAL = {
    'todos': 'Total neto (entradas − reembolsos − contracargos)',
    'stripe': 'Total en la cuenta (tarjeta − reembolsos − contracargos)',
    'tarjeta': 'Total tarjeta',
    'efectivo': 'Total efectivo',
    'transferencia': 'Total transferencia',
    'reembolsos': 'Total reembolsos',
    'contracargos': 'Total contracargos perdidos',
}


def _parse_fecha(valor):
    """Parsea una fecha AAAA-MM-DD. Si es inválida o vacía, devuelve None."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor.strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _describir_filtro(concepto, desde, hasta, moneda):
    """Construye una descripción legible del filtro en una sola línea.

    Ejemplo: «Tarjeta · 1 oct 2026 — 31 oct 2026 · MXN»
    """
    partes = [CONCEPTOS_MOVIMIENTOS.get(concepto, 'Todos los conceptos')]

    if desde and hasta:
        if desde == hasta:
            partes.append(formats.date_format(desde, 'j M Y'))
        else:
            partes.append(f"{formats.date_format(desde, 'j M Y')} — {formats.date_format(hasta, 'j M Y')}")
    elif desde:
        partes.append(f"Desde {formats.date_format(desde, 'j M Y')}")
    elif hasta:
        partes.append(f"Hasta {formats.date_format(hasta, 'j M Y')}")
    else:
        partes.append("Todo el histórico")

    if moneda:
        partes.append(moneda)

    return ' · '.join(partes)


def movimientos_financieros(request):
    """Detalle de movimientos de dinero por reserva.

    Muestra filas individuales de tarjeta, efectivo, transferencia y reembolsos.
    Acceso exclusivo para jefes y operadores de plataforma.
    """
    if not puede_ver_finanzas(request):
        raise PermissionDenied

    operador = scope.es_operador_plataforma(request.user)
    empresa = None if operador else scope.empresa_actual(request)

    desde = _parse_fecha(request.GET.get('desde'))
    hasta = _parse_fecha(request.GET.get('hasta'))

    concepto = request.GET.get('concepto', 'todos')
    if concepto not in CONCEPTOS_MOVIMIENTOS:
        concepto = 'todos'

    moneda = request.GET.get('moneda', '').strip().upper()
    if moneda not in ('MXN', 'USD'):
        moneda = None

    filas_todas = movimientos(
        desde=desde,
        hasta=hasta,
        concepto=concepto,
        moneda=moneda,
        empresa=empresa,
    )

    totales = totales_de_movimientos(
        filas_todas,
        concepto=concepto,
        moneda=moneda,
    )

    paginator = Paginator(filas_todas, 50)
    pagina = request.GET.get('pagina', 1)
    page_obj = paginator.get_page(pagina)

    filtro_desc = _describir_filtro(concepto, desde, hasta, moneda)
    etiqueta_tot = ETIQUETAS_TOTAL.get(concepto, 'Total')

    return render(request, 'finance/movimientos.html', {
        **admin.site.each_context(request),
        'title': 'Movimientos',
        'filas': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'totales': totales,
        'desde': desde,
        'hasta': hasta,
        'desde_str': request.GET.get('desde', ''),
        'hasta_str': request.GET.get('hasta', ''),
        'concepto': concepto,
        'conceptos': CONCEPTOS_MOVIMIENTOS,
        'moneda': moneda or '',
        'filtro_descripcion': filtro_desc,
        'etiqueta_total': etiqueta_tot,
    })
