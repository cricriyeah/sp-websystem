"""Registro de estrategias de cupo, llaveado por Servicio.estrategia_cupo."""
import logging

from .estrategias import BajoDemanda, EstrategiaCupo, ModoOcupacion, PorNoche, PorRecursoDia

logger = logging.getLogger(__name__)
REGISTRO_ESTRATEGIAS: dict[str, EstrategiaCupo] = {
    'por_recurso_dia': PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO),
    'por_noche': PorNoche(),
    'bajo_demanda': BajoDemanda(),
}
_DEFAULT = 'por_recurso_dia'


def registrar_estrategia(clave: str, estrategia: EstrategiaCupo) -> None:
    REGISTRO_ESTRATEGIAS[clave] = estrategia


def obtener_estrategia(clave: str = _DEFAULT) -> EstrategiaCupo:
    est = REGISTRO_ESTRATEGIAS.get(clave)
    if est is None:
        logger.warning('estrategia_cupo desconocida %r, se usa %r', clave, _DEFAULT)
        est = REGISTRO_ESTRATEGIAS[_DEFAULT]
    return est
