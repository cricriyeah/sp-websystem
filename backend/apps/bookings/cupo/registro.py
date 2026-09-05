"""Registro centralizado de estrategias de cupo por tipo de servicio (ADR-003)."""

from .estrategias import BajoDemanda, EstrategiaCupo, ModoOcupacion, PorNoche, PorRecursoDia

REGISTRO_ESTRATEGIAS: dict[str, EstrategiaCupo] = {
    'pesca': PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO),
    'paseo_exclusivo': PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO),
    'paseo_compartido': PorRecursoDia(modo=ModoOcupacion.COMPARTIDO),
    'por_noche': PorNoche(),
    'hospedaje': PorNoche(),
    'bajo_demanda': BajoDemanda(),
    'default': PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO),
}


def registrar_estrategia(tipo_servicio: str, estrategia: EstrategiaCupo) -> None:
    """Registra una nueva estrategia para un tipo de servicio."""
    REGISTRO_ESTRATEGIAS[tipo_servicio] = estrategia


def obtener_estrategia(tipo_servicio: str = 'default') -> EstrategiaCupo:
    """Obtiene la estrategia asociada a un tipo de servicio o el default."""
    estrategia = REGISTRO_ESTRATEGIAS.get(tipo_servicio)
    if estrategia is None:
        estrategia = REGISTRO_ESTRATEGIAS.get('default')
    return estrategia
