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
