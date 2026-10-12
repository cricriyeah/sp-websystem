"""Lógica del apartado temporal de cupo en el checkout web."""

from collections import defaultdict
from datetime import date
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.fleet.calendario_paquete import fechas_de_componente


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


def habitaciones_apartadas(
    empresa,
    desde: date,
    hasta: date,
    excluir_pk: int | None = None,
    servicio_id: int | None = None,
) -> dict[int, list[tuple[date, date]]]:
    """Devuelve un mapeo de recurso_id -> lista de intervalos (inicio, fin)

    para las entradas 'habitaciones' de los retratos vigentes que traslapan [desde, hasta).
    """
    if not apartado_activo():
        return {}

    qs = reservas_con_apartado_vigente(empresa)
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)

    ocupaciones_por_recurso: dict[int, list[tuple[date, date]]] = defaultdict(list)

    for demanda in qs.values_list('apartado_demanda', flat=True):
        if not isinstance(demanda, dict):
            continue
        habitaciones = demanda.get('habitaciones', [])
        if not isinstance(habitaciones, list):
            continue
        for hab in habitaciones:
            if not isinstance(hab, dict):
                continue
            if servicio_id is not None and str(hab.get('servicio_id')) != str(servicio_id):
                continue
            rec_id = hab.get('recurso_id')
            if rec_id is None:
                continue
            ini_val = hab.get('inicio')
            fin_val = hab.get('fin')
            try:
                o_ini = date.fromisoformat(ini_val) if isinstance(ini_val, str) else ini_val
                o_fin = date.fromisoformat(fin_val) if isinstance(fin_val, str) else fin_val
            except (ValueError, TypeError):
                continue
            if o_ini < hasta and o_fin > desde:
                ocupaciones_por_recurso[int(rec_id)].append((o_ini, o_fin))

    return dict(ocupaciones_por_recurso)


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


def construir_retrato_hospedaje(reserva) -> dict[str, Any]:
    """Arma el retrato de demanda para una reserva de hospedaje directo.

    Usa `elegir_habitaciones` para seleccionar las habitaciones.
    Lanza `SinCupoError` si no hay habitaciones disponibles para el grupo.
    """
    from . import SinCupoError
    from .confirmacion import elegir_habitaciones

    if not reserva.servicio or reserva.servicio.estrategia_cupo != 'por_noche':
        return {"v": 1, "salidas": [], "habitaciones": []}

    desde = reserva.fecha
    hasta = reserva.fecha_fin_servicio
    personas = reserva.numero_personas

    elegidos = elegir_habitaciones(
        servicio=reserva.servicio,
        desde=desde,
        hasta=hasta,
        personas=personas,
        empresa=reserva.empresa,
        excluir_pk=reserva.pk,
    )
    if not elegidos:
        raise SinCupoError('No hay habitación disponible en esas fechas.')

    desde_str = desde.isoformat() if hasattr(desde, 'isoformat') else str(desde)
    hasta_str = hasta.isoformat() if hasattr(hasta, 'isoformat') else str(hasta)
    habitaciones = [
        {
            "recurso_id": rec_id,
            "inicio": desde_str,
            "fin": hasta_str,
            "servicio_id": reserva.servicio_id,
        }
        for rec_id in elegidos
    ]
    return {
        "v": 1,
        "salidas": [],
        "habitaciones": habitaciones,
    }


def construir_retrato_paquete(reserva) -> dict[str, Any]:
    """Arma el retrato de demanda para una reserva de paquete de una sola empresa.

    Refleja la lista de validación de actividades de mar (estrategia 'por_recurso_dia')
    y hospedaje (estrategia 'por_noche') que reservar_cupo_al_confirmar validaría
    para esa reserva.
    Un paquete sin componentes de mar ni hospedaje devuelve salidas: [], habitaciones: [].
    Lanza `SinCupoError` si un componente de hospedaje no tiene habitaciones disponibles.
    """
    from . import SinCupoError
    from .confirmacion import elegir_habitaciones

    if not getattr(reserva, 'paquete_id', None) and not getattr(reserva, 'paquete', None):
        return {"v": 1, "salidas": [], "habitaciones": []}

    if getattr(reserva, 'orden_id', None) is not None:
        return {"v": 1, "salidas": [], "habitaciones": []}

    paquete = reserva.paquete
    if paquete is None or not hasattr(paquete, 'servicios_asociados'):
        return {"v": 1, "salidas": [], "habitaciones": []}

    componentes = list(
        paquete.servicios_asociados.select_related('servicio').order_by('orden')
    )

    salidas: list[dict[str, Any]] = []
    habitaciones: list[dict[str, Any]] = []

    for ps in componentes:
        servicio = ps.servicio
        if servicio.estrategia_cupo == 'por_recurso_dia':
            personas = reserva.personas_de(servicio.pk)
            fechas = (
                sorted(fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas))
                if ps.salidas > 1 else [reserva.fecha]
            )
            for dia in fechas:
                fecha_str = dia.isoformat() if hasattr(dia, 'isoformat') else str(dia)
                salidas.append({
                    "fecha": fecha_str,
                    "personas": int(personas),
                    "servicio_id": servicio.pk,
                })
        elif servicio.estrategia_cupo == 'por_noche':
            desde = reserva.fecha_inicio_paquete
            hasta = reserva.fecha_fin_servicio
            personas = reserva.personas_de(servicio.pk)
            elegidos = elegir_habitaciones(
                servicio=servicio,
                desde=desde,
                hasta=hasta,
                personas=personas,
                empresa=reserva.empresa,
                excluir_pk=reserva.pk,
            )
            if not elegidos:
                raise SinCupoError(
                    f'No hay habitación disponible para el componente {servicio.nombre}.'
                )
            desde_str = desde.isoformat() if hasattr(desde, 'isoformat') else str(desde)
            hasta_str = hasta.isoformat() if hasattr(hasta, 'isoformat') else str(hasta)
            for rec_id in elegidos:
                habitaciones.append({
                    "recurso_id": rec_id,
                    "inicio": desde_str,
                    "fin": hasta_str,
                    "servicio_id": servicio.pk,
                })

    return {
        "v": 1,
        "salidas": salidas,
        "habitaciones": habitaciones,
    }
