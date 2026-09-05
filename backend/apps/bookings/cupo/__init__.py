"""Módulo de cupo y disponibilidad de reservas."""

from .adaptador import (
    ContextoCupo,
    ContextoCupoRango,
    obtener_contexto_cupo,
    obtener_contexto_rango,
)
from .candado import (
    bloquear_cupo,
    bloquear_cupo_del_dia,
    calcular_clave_candado,
)
from .estrategias import (
    DemandaCupo,
    EstrategiaCupo,
    ModoOcupacion,
    PorRecursoDia,
    ResultadoDisponibilidad,
)
from .nucleo import (
    MODO_COMPARTIDO,
    MODO_EXCLUSIVO,
    MOTIVO_LLENO,
    MOTIVO_SIN_LUGAR,
    MOTIVO_SIN_PANGA,
    caben,
    caben_compartido,
    motivo_sin_lugar,
    ocupacion_por_rango,
)
from .registro import (
    REGISTRO_ESTRATEGIAS,
    obtener_estrategia,
    registrar_estrategia,
)

__all__ = [
    'ContextoCupo',
    'ContextoCupoRango',
    'obtener_contexto_cupo',
    'obtener_contexto_rango',
    'DemandaCupo',
    'EstrategiaCupo',
    'ModoOcupacion',
    'PorRecursoDia',
    'ResultadoDisponibilidad',
    'MODO_EXCLUSIVO',
    'MODO_COMPARTIDO',
    'MOTIVO_LLENO',
    'MOTIVO_SIN_PANGA',
    'MOTIVO_SIN_LUGAR',
    'bloquear_cupo',
    'bloquear_cupo_del_dia',
    'calcular_clave_candado',
    'caben',
    'caben_compartido',
    'motivo_sin_lugar',
    'ocupacion_por_rango',
    'REGISTRO_ESTRATEGIAS',
    'obtener_estrategia',
    'registrar_estrategia',
]
