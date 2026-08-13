"""Panel de dinero. Solo jefes.

Va montado dentro del admin (`/admin/finanzas/`, ver `config/urls.py`) para
heredar su sesion, su menu y su login — no es una app aparte con su propia
autenticacion.
"""
from calendar import monthrange
from datetime import date

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .services import balances_por_dia, resumen


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
    mes = _mes_pedido(request, hoy)
    ultimo_dia = mes.replace(day=monthrange(mes.year, mes.month)[1])
    siguiente = _mes_vecino(mes, 1)

    return render(request, 'finance/panel.html', {
        **admin.site.each_context(request),
        'title': 'Finanzas',
        'hoy': hoy,
        **resumen(hoy),
        'mes_visto': mes,
        'mes_anterior': _mes_vecino(mes, -1),
        # Sin boton para adelantarse a meses que todavia no pasan.
        'mes_siguiente': siguiente if siguiente <= hoy.replace(day=1) else None,
        'dias': balances_por_dia(mes, ultimo_dia),
    })
