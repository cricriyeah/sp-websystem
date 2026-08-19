"""Panel de dinero. Solo jefes.

Va montado dentro del admin (`/admin/finanzas/`, ver `config/urls.py`) para
heredar su sesion, su menu y su login — no es una app aparte con su propia
autenticacion.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

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


@dataclass(frozen=True)
class Barra:
    """Un dia de la grafica de entradas."""

    dia: date
    monto: Decimal
    # Porcentaje contra el dia mas alto del periodo, que es lo unico que necesita
    # la plantilla para dibujar la barra con una clase de altura.
    altura: int


def _altura(monto, maximo):
    """Porcentaje de la barra, con piso de 1 para el dinero que si entro.

    500 pesos contra un dia de 100 mil redondean a 0 y la barra desaparece: se ve
    igual que un dia en el que no entro nada, que es justo lo contrario de lo que
    paso. Un 1% no distorsiona la comparacion y salva el dato. El cero se reserva
    para los dias vacios de verdad.
    """
    if not monto:
        return 0
    return max(1, round(monto / maximo * 100))


def _grafica_de_entradas(desde, hasta):
    """`{moneda: [Barra, ...]}` con una barra por cada dia del rango.

    Se incluyen los dias sin movimiento a proposito. El historico de abajo si los
    omite —ahi cada renglon es un dato y una fila vacia es ruido—, pero en una
    grafica el hueco *es* el dato: se ve de un golpe que ese dia no entro nada.

    Cada moneda va por separado y nunca se suman: el sistema no guarda tipo de
    cambio, asi que un total mezclado seria un numero inventado. Una moneda sin
    un solo movimiento en el periodo no aparece, para no dibujar una grafica plana
    de dolares en un negocio que ese mes solo cobro en pesos.
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

    grafica = {}
    for moneda in sorted(monedas):
        montos = [entradas_por_dia.get(dia, {}).get(moneda, Decimal(0)) for dia in dias]
        # El maximo nunca es cero aqui: la moneda esta en `monedas` justamente
        # porque tuvo al menos un dia con entradas.
        maximo = max(montos)
        grafica[moneda] = [
            Barra(dia=dia, monto=monto, altura=_altura(monto, maximo))
            for dia, monto in zip(dias, montos)
        ]
    return grafica


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
