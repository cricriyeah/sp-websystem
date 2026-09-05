"""Módulo de cupo y disponibilidad de reservas."""

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

__all__ = [
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
    'caben',
    'caben_compartido',
    'motivo_sin_lugar',
    'ocupacion_por_rango',
]
