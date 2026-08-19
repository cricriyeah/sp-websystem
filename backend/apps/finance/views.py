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
from django.shortcuts import render
from django.utils import formats

from .services import balances, balances_por_dia, resumen


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


def _grafica_de_entradas(desde, hasta):
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
        for dia, por_moneda in balances_por_dia(desde, hasta)
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
    """Entradas, salidas y balance del dia, del mes y del año.

    Restringido a superusuarios: es la unica pantalla con la foto completa del
    dinero. La vendedora no la ve, igual que no ve `fleet.Tarifa`
    (ver docs/contexto-negocio.md, seccion Roles y permisos).
    """
    if not request.user.is_superuser:
        raise PermissionDenied

    hoy = date.today()
    periodo = request.GET.get('periodo', PERIODO_DEFAULT)
    if periodo not in dict(PERIODOS):
        periodo = PERIODO_DEFAULT
    desde, hasta = rango_del_periodo(periodo, hoy)

    mes = _mes_pedido(request, hoy)
    ultimo_dia = mes.replace(day=monthrange(mes.year, mes.month)[1])
    siguiente = _mes_vecino(mes, 1)

    return render(request, 'finance/panel.html', {
        **admin.site.each_context(request),
        'title': 'Finanzas',
        'hoy': hoy,
        **resumen(hoy),
        # El periodo elegido en el select: filtra el balance de arriba y la
        # grafica. El historico de abajo sigue siendo mes a mes con sus flechas,
        # que es lo unico que deja llegar a un mes viejo cualquiera.
        'periodos': PERIODOS,
        'periodo': periodo,
        'periodo_etiqueta': dict(PERIODOS)[periodo],
        'periodo_desde': desde,
        'periodo_hasta': hasta,
        'saldo_periodo': balances(desde, hasta),
        'grafica': _grafica_de_entradas(desde, hasta),
        'mes_visto': mes,
        'mes_anterior': _mes_vecino(mes, -1),
        # Sin boton para adelantarse a meses que todavia no pasan.
        'mes_siguiente': siguiente if siguiente <= hoy.replace(day=1) else None,
        'dias': balances_por_dia(mes, ultimo_dia),
    })
