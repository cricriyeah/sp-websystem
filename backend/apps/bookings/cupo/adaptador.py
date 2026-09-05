"""Adaptador que resuelve los datos del ORM para alimentar a las estrategias de cupo."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ContextoCupo:
    """Datos de ocupación, recursos y límites para una fecha específica."""
    grupos: list[int]
    capacidades: list[int]
    tope: int


@dataclass(frozen=True)
class ContextoCupoRango:
    """Datos de ocupación, recursos y límites para un rango de fechas."""
    fechas: list[date]
    grupos_por_fecha: dict[date, list[int]]
    capacidades_por_fecha: dict[date, list[int]]
    topes_por_fecha: dict[date, int]


def obtener_contexto_cupo(fecha: date, empresa, excluir_pk: int | None = None) -> ContextoCupo:
    """Obtiene el contexto de cupo para un día resolviendo reservas y flota de La Paz."""
    from apps.bookings.models import CUPO_MAXIMO_DEFAULT, ESTADOS_QUE_OCUPAN_CUPO, CupoDiario, Reserva
    from apps.fleet.models import capacidades_disponibles

    ocupadas = Reserva.objects.filter(
        fecha=fecha,
        estado__in=ESTADOS_QUE_OCUPAN_CUPO,
        empresa=empresa,
    )
    if excluir_pk is not None:
        ocupadas = ocupadas.exclude(pk=excluir_pk)

    grupos = list(ocupadas.values_list('numero_personas', flat=True))
    capacidades = capacidades_disponibles(fecha, empresa)

    override = CupoDiario.objects.filter(fecha=fecha, empresa=empresa).first()
    tope = override.cupo_maximo if override else CUPO_MAXIMO_DEFAULT

    return ContextoCupo(grupos=grupos, capacidades=capacidades, tope=tope)


def obtener_contexto_rango(desde: date, hasta: date, empresa) -> ContextoCupoRango:
    """Obtiene el contexto para un rango de fechas en 4 consultas optimizadas."""
    from apps.bookings.models import CUPO_MAXIMO_DEFAULT, ESTADOS_QUE_OCUPAN_CUPO, CupoDiario, Reserva
    from apps.fleet.models import capacidades_por_fecha

    fechas = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]

    grupos_por_fecha = defaultdict(list)
    for fecha, personas_de_esa in Reserva.objects.filter(
        fecha__range=(desde, hasta),
        estado__in=ESTADOS_QUE_OCUPAN_CUPO,
        empresa=empresa,
    ).values_list('fecha', 'numero_personas'):
        grupos_por_fecha[fecha].append(personas_de_esa)

    topes = dict(
        CupoDiario.objects.filter(fecha__range=(desde, hasta), empresa=empresa)
        .values_list('fecha', 'cupo_maximo')
    )
    topes_por_fecha = {fecha: topes.get(fecha, CUPO_MAXIMO_DEFAULT) for fecha in fechas}

    capacidades = capacidades_por_fecha(desde, hasta, empresa)

    return ContextoCupoRango(
        fechas=fechas,
        grupos_por_fecha=dict(grupos_por_fecha),
        capacidades_por_fecha=capacidades,
        topes_por_fecha=topes_por_fecha,
    )


def obtener_recursos_con_ocupaciones(
    desde: date,
    hasta: date,
    empresa,
    servicio=None,
    excluir_pk: int | None = None,
) -> list[tuple[int, int, list[tuple[date, date]]]]:
    """Obtiene los recursos activos de la empresa y sus ocupaciones registradas en [desde, hasta).

    Retorna una lista de tuplas: (recurso_id, capacidad_maxima, [(o_ini, o_fin), ...]).
    """
    from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, ReservaOcupacion
    from apps.fleet.models import Recurso

    recursos_qs = Recurso.objects.filter(empresa=empresa, activo=True)
    if servicio is not None:
        recursos_qs = recursos_qs.filter(servicio=servicio)

    recursos = list(recursos_qs)
    if not recursos:
        return []

    ocupaciones_qs = ReservaOcupacion.objects.filter(
        empresa=empresa,
        recurso__in=recursos,
        reserva__estado__in=ESTADOS_QUE_OCUPAN_CUPO,
        fecha_inicio__lt=hasta,
        fecha_fin__gt=desde,
    )
    if excluir_pk is not None:
        ocupaciones_qs = ocupaciones_qs.exclude(reserva_id=excluir_pk)

    ocupaciones_por_recurso = defaultdict(list)
    for r_id, o_ini, o_fin in ocupaciones_qs.values_list('recurso_id', 'fecha_inicio', 'fecha_fin'):
        ocupaciones_por_recurso[r_id].append((o_ini, o_fin))

    return [
        (r.id, r.capacidad_maxima, ocupaciones_por_recurso[r.id])
        for r in recursos
    ]


def evaluar_disponibilidad_hospedaje(
    check_in: date,
    check_out: date,
    personas: int,
    empresa,
    servicio=None,
    cantidad_recursos: int = 1,
    excluir_pk: int | None = None,
) -> bool:
    """Consulta si hay recursos suficientes disponibles para una estadía multidía."""
    from .estrategias import DemandaCupo, PorNoche

    recursos_con_ocupaciones = obtener_recursos_con_ocupaciones(
        desde=check_in,
        hasta=check_out,
        empresa=empresa,
        servicio=servicio,
        excluir_pk=excluir_pk,
    )
    demanda = DemandaCupo(
        fecha=check_in,
        fecha_fin=check_out,
        personas=personas,
        cantidad_recursos=cantidad_recursos,
        excluir_pk=excluir_pk,
    )
    estrategia = PorNoche()
    resultado = estrategia.evaluar_ocupacion(demanda, recursos_con_ocupaciones)
    return resultado.disponible

