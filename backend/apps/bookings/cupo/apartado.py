"""Lógica del apartado temporal de cupo en el checkout web."""

from collections import defaultdict
from datetime import date
from typing import Any

from django.conf import settings
from django.utils import timezone


def apartado_activo() -> bool:
    """True si el ajuste APARTADO_MINUTOS es mayor que 0.

    Lee directamente de settings en cada llamada para respetar override_settings.
    """
    return getattr(settings, 'APARTADO_MINUTOS', 0) > 0


def reservas_con_apartado_vigente(empresa, ahora=None):
    """Queryset de reservas pendiente_pago de esa empresa con apartado_hasta > ahora y apartado_demanda no nulo."""
    from apps.bookings.models import Reserva

    if not apartado_activo():
        return Reserva.objects.none()

    if ahora is None:
        ahora = timezone.now()

    return Reserva.objects.filter(
        empresa=empresa,
        estado=Reserva.Estado.PENDIENTE_PAGO,
        apartado_hasta__gt=ahora,
        apartado_demanda__isnull=False,
    )


def demanda_apartada_del_dia(
    empresa,
    fecha: date,
    excluir_pk: int | None = None,
    servicio_id: int | None = None,
) -> list[int]:
    """Devuelve la lista de personas por grupo para las entradas 'salidas'

    de los retratos vigentes cuya fecha coincide (excluyendo excluir_pk).
    """
    if not apartado_activo():
        return []

    qs = reservas_con_apartado_vigente(empresa)
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)

    fecha_str = fecha.isoformat() if hasattr(fecha, 'isoformat') else str(fecha)
    grupos: list[int] = []

    for demanda in qs.values_list('apartado_demanda', flat=True):
        if not isinstance(demanda, dict):
            continue
        salidas = demanda.get('salidas', [])
        if not isinstance(salidas, list):
            continue
        for salida in salidas:
            if not isinstance(salida, dict):
                continue
            if salida.get('fecha') != fecha_str:
                continue
            if servicio_id is not None and salida.get('servicio_id') != servicio_id:
                continue
            personas = salida.get('personas')
            if personas is not None:
                grupos.append(int(personas))

    return grupos


def demanda_apartada_por_rango(
    empresa,
    desde: date,
    hasta: date,
    excluir_pk: int | None = None,
    servicio_id: int | None = None,
) -> dict[date, list[int]]:
    """Devuelve un mapeo de fecha -> lista de personas por grupo para las entradas 'salidas'
    de los retratos vigentes en el rango [desde, hasta] (excluyendo excluir_pk).

    Carga los retratos vigentes de la empresa en UNA sola consulta.
    """
    if not apartado_activo():
        return {}

    qs = reservas_con_apartado_vigente(empresa)
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)

    grupos_por_fecha: dict[date, list[int]] = defaultdict(list)

    for demanda in qs.values_list('apartado_demanda', flat=True):
        if not isinstance(demanda, dict):
            continue
        salidas = demanda.get('salidas', [])
        if not isinstance(salidas, list):
            continue
        for salida in salidas:
            if not isinstance(salida, dict):
                continue
            fecha_val = salida.get('fecha')
            if not fecha_val:
                continue
            if servicio_id is not None and salida.get('servicio_id') != servicio_id:
                continue
            try:
                fecha_salida = date.fromisoformat(fecha_val) if isinstance(fecha_val, str) else fecha_val
            except (ValueError, TypeError):
                continue
            if desde <= fecha_salida <= hasta:
                personas = salida.get('personas')
                if personas is not None:
                    grupos_por_fecha[fecha_salida].append(int(personas))

    return dict(grupos_por_fecha)


def construir_retrato_servicio_suelto(reserva) -> dict[str, Any]:
    """Arma el retrato de demanda para una reserva de servicio suelto."""
    fecha_str = reserva.fecha.isoformat() if hasattr(reserva.fecha, 'isoformat') else str(reserva.fecha)
    return {
        "v": 1,
        "salidas": [
            {
                "fecha": fecha_str,
                "personas": int(reserva.numero_personas),
                "servicio_id": reserva.servicio_id,
            }
        ],
        "habitaciones": [],
    }
