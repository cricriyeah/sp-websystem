"""Módulo de cupo y disponibilidad de reservas."""


class SinCupoError(Exception):
    """Lanzada cuando no hay cupo o recursos disponibles al confirmar un pago."""
    pass


from .adaptador import (
    ContextoCupo,
    ContextoCupoRango,
    evaluar_disponibilidad_hospedaje,
    obtener_contexto_cupo,
    obtener_contexto_rango,
    obtener_recursos_con_ocupaciones,
    solo_demanda_de_mar,
)
from .apartado import (
    apartado_activo,
    construir_retrato_hospedaje,
    construir_retrato_paquete,
    construir_retrato_servicio_suelto,
    demanda_apartada_del_dia,
    demanda_apartada_por_rango,
    habitaciones_apartadas,
    reservas_con_apartado_vigente,
)
from .candado import (
    bloquear_cupo,
    bloquear_cupo_del_dia,
    bloquear_recurso,
    calcular_clave_candado,
    calcular_clave_recurso,
)
from .confirmacion import (
    elegir_habitaciones,
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

__all__ = [
    'ContextoCupo',
    'ContextoCupoRango',
    'evaluar_disponibilidad_hospedaje',
    'obtener_contexto_cupo',
    'obtener_contexto_rango',
    'solo_demanda_de_mar',
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
    'elegir_habitaciones',
    'motivo_sin_lugar',
    'ocupacion_por_rango',
    'rango_traslapa',
    'recursos_disponibles_en_rango',
    'REGISTRO_ESTRATEGIAS',
    'obtener_estrategia',
    'registrar_estrategia',
    'apartado_activo',
    'construir_retrato_hospedaje',
    'construir_retrato_paquete',
    'construir_retrato_servicio_suelto',
    'demanda_apartada_del_dia',
    'demanda_apartada_por_rango',
    'habitaciones_apartadas',
    'reservas_con_apartado_vigente',
]

