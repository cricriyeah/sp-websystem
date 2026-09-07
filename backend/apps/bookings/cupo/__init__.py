"""Módulo de cupo y disponibilidad de reservas."""

from .adaptador import (
    ContextoCupo,
    ContextoCupoRango,
    evaluar_disponibilidad_hospedaje,
    obtener_contexto_cupo,
    obtener_contexto_rango,
    obtener_recursos_con_ocupaciones,
)
from .candado import (
    bloquear_cupo,
    bloquear_cupo_del_dia,
    bloquear_recurso,
    calcular_clave_candado,
    calcular_clave_recurso,
)
from .estrategias import (
    BajoDemanda,
    DemandaCupo,
    EstrategiaCupo,
    ModoOcupacion,
    PorNoche,
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
    elegir_recursos,
    motivo_sin_lugar,
    ocupacion_por_rango,
    rango_traslapa,
    recursos_disponibles_en_rango,
)
from .registro import (
    REGISTRO_ESTRATEGIAS,
    obtener_estrategia,
    registrar_estrategia,
)


class SinCupoError(Exception):
    """Lanzada cuando no hay cupo o recursos disponibles al confirmar un pago."""
    pass


__all__ = [
    'ContextoCupo',
    'ContextoCupoRango',
    'evaluar_disponibilidad_hospedaje',
    'obtener_contexto_cupo',
    'obtener_contexto_rango',
    'obtener_recursos_con_ocupaciones',
    'DemandaCupo',
    'EstrategiaCupo',
    'ModoOcupacion',
    'PorNoche',
    'PorRecursoDia',
    'BajoDemanda',
    'ResultadoDisponibilidad',
    'MODO_EXCLUSIVO',
    'MODO_COMPARTIDO',
    'MOTIVO_LLENO',
    'MOTIVO_SIN_PANGA',
    'MOTIVO_SIN_LUGAR',
    'bloquear_cupo',
    'bloquear_cupo_del_dia',
    'bloquear_recurso',
    'calcular_clave_candado',
    'calcular_clave_recurso',
    'SinCupoError',
    'caben',
    'caben_compartido',
    'elegir_recursos',
    'motivo_sin_lugar',
    'ocupacion_por_rango',
    'rango_traslapa',
    'recursos_disponibles_en_rango',
    'REGISTRO_ESTRATEGIAS',
    'obtener_estrategia',
    'registrar_estrategia',
]

