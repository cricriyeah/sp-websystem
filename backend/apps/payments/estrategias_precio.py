"""Estrategias de precio puras y tipadas (ADR-003).

Desacopla el calculo del precio base de una experiencia de la tabla Tarifa
singleton. Cada estrategia recibe la configuracion del servicio y la demanda del
cliente (personas, moneda, noches), calculando el monto en Decimal cuantizado a centavos.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from apps.fleet.tarifa_transporte import TarifaTransporteNoConfigurada, resolver_tarifa_transporte
from .pricing import CENTAVOS, PERSONAS_INCLUIDAS, cargo_por_personas, personas_extra


class TipoEstrategiaPrecio(StrEnum):
    POR_GRUPO = 'por_grupo'
    POR_PERSONA = 'por_persona'
    TARIFA_FIJA = 'tarifa_fija'
    POR_NOCHE = 'por_noche'
    POR_RUTA = 'por_ruta'


@dataclass(frozen=True)
class DemandaPrecio:
    """Demanda para cotizar el precio base de un servicio."""
    personas: int
    moneda: str = 'MXN'
    noches: int = 1
    tipo_traslado: str | None = None
    zona: str | None = None

    @property
    def moneda_normalizada(self) -> str:
        return (self.moneda or 'MXN').upper()


def _obtener_campo(config: Any, nombres: list[str]) -> Any:
    """Extrae el primer atributo o clave coincidente del objeto o diccionario de configuracion."""
    if isinstance(config, dict):
        for n in nombres:
            if n in config and config[n] is not None:
                return config[n]
        return None
    for n in nombres:
        if hasattr(config, n):
            val = getattr(config, n)
            if val is not None:
                return val
    return None


def resolver_precio_base(servicio_config: Any, moneda: str) -> Decimal:
    """Obtiene el precio base configurado para la moneda especificada."""
    moneda_norm = (moneda or 'MXN').upper()
    if moneda_norm == 'USD':
        val = _obtener_campo(servicio_config, ['precio_base_usd', 'precio_usd'])
    else:
        val = _obtener_campo(servicio_config, ['precio_base', 'precio'])

    if val is None:
        raise ValueError(f"No hay precio configurado en {moneda_norm}.")
    return Decimal(val)


def resolver_precio_persona_extra(servicio_config: Any, moneda: str) -> Decimal | None:
    """Obtiene el cargo por persona adicional configurado en la moneda."""
    moneda_norm = (moneda or 'MXN').upper()
    if moneda_norm == 'USD':
        val = _obtener_campo(servicio_config, ['precio_persona_extra_usd'])
    else:
        val = _obtener_campo(servicio_config, ['precio_persona_extra'])

    if val is None:
        return None
    return Decimal(val)


def resolver_personas_incluidas(servicio_config: Any) -> int:
    """Obtiene la cantidad de personas incluidas en el precio base antes de cobrar extras."""
    val = _obtener_campo(servicio_config, ['personas_incluidas'])
    if val is not None:
        return int(val)
    return PERSONAS_INCLUIDAS


class EstrategiaPrecio(ABC):
    """Contrato base para todas las estrategias de precio."""
    clave: str = ''

    @abstractmethod
    def calcular_base(self, servicio_config: Any, demanda: DemandaPrecio) -> Decimal:
        """Calcula el precio base del servicio segun la demanda y configuracion."""
        pass


class PorGrupo(EstrategiaPrecio):
    """Precio plano por grupo (embarcacion completa) mas recargo por personas extra."""
    clave = TipoEstrategiaPrecio.POR_GRUPO

    def calcular_base(self, servicio_config: Any, demanda: DemandaPrecio) -> Decimal:
        moneda = demanda.moneda_normalizada
        base = resolver_precio_base(servicio_config, moneda)
        incluidas = resolver_personas_incluidas(servicio_config)
        extras = personas_extra(demanda.personas, personas_incluidas=incluidas)

        if extras > 0:
            precio_extra = resolver_precio_persona_extra(servicio_config, moneda)
            if precio_extra is None:
                raise ValueError(f"No hay cargo por persona extra configurado en {moneda}.")
            recargo = cargo_por_personas(precio_extra, demanda.personas, personas_incluidas=incluidas)
        else:
            recargo = Decimal('0')

        total = (base + recargo).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        return total


class PorPersona(EstrategiaPrecio):
    """Precio unitario por persona multiplicado por el numero de personas."""
    clave = TipoEstrategiaPrecio.POR_PERSONA

    def calcular_base(self, servicio_config: Any, demanda: DemandaPrecio) -> Decimal:
        moneda = demanda.moneda_normalizada
        base = resolver_precio_base(servicio_config, moneda)
        personas = max(1, demanda.personas)
        total = (base * Decimal(personas)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        return total


class TarifaFija(EstrategiaPrecio):
    """Tarifa plana independiente de las personas o la duracion."""
    clave = TipoEstrategiaPrecio.TARIFA_FIJA

    def calcular_base(self, servicio_config: Any, demanda: DemandaPrecio) -> Decimal:
        moneda = demanda.moneda_normalizada
        base = resolver_precio_base(servicio_config, moneda)
        return Decimal(base).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


class PorNoche(EstrategiaPrecio):
    """Precio por noche multiplicado por la cantidad de noches solicitadas."""
    clave = TipoEstrategiaPrecio.POR_NOCHE

    def calcular_base(self, servicio_config: Any, demanda: DemandaPrecio) -> Decimal:
        moneda = demanda.moneda_normalizada
        base = resolver_precio_base(servicio_config, moneda)
        noches = max(1, demanda.noches)
        total = (base * Decimal(noches)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        return total


class PorRuta(EstrategiaPrecio):
    """Precio de un traslado: la fila de TransporteTarifa que aplica a
    (tipo_traslado, zona, personas). El precio sale entero de la tabla —
    no usa precio_base ni personas_incluidas del Servicio."""
    clave = TipoEstrategiaPrecio.POR_RUTA

    def calcular_base(self, servicio_config: Any, demanda: DemandaPrecio) -> Decimal:
        tarifas = _obtener_campo(servicio_config, ['tarifas_transporte_activas'])
        if tarifas is None:
            raise ValueError('PorRuta necesita servicio_config.tarifas_transporte_activas')
        if not demanda.tipo_traslado:
            raise ValueError('PorRuta necesita demanda.tipo_traslado')
        try:
            fila = resolver_tarifa_transporte(
                tarifas, tipo_traslado=demanda.tipo_traslado,
                zona=demanda.zona, personas=demanda.personas,
            )
        except TarifaTransporteNoConfigurada as e:
            raise ValueError(str(e)) from e
        precio = fila.precio_en(demanda.moneda_normalizada)
        if precio is None:
            raise ValueError(f'La tarifa no tiene precio en {demanda.moneda_normalizada}.')
        return Decimal(precio).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def demanda_traslado(detalle, personas, moneda):
    """La misma demanda para preparar el cobro y verificar su snapshot."""
    return DemandaPrecio(
        personas=personas, moneda=moneda,
        tipo_traslado=detalle.tipo_traslado, zona=detalle.zona_efectiva(),
    )


@dataclass(frozen=True)
class _TarifaRutaCongelada:
    """Fila en memoria del precio aceptado, independiente del catalogo actual."""
    tipo_traslado: str
    zona: str
    personas_min: int
    personas_max: int
    precio: Decimal
    moneda: str

    def precio_en(self, moneda):
        return self.precio if moneda == self.moneda else None


def precio_traslado_congelado(detalle, moneda):
    """Verifica con PorRuta y las personas/precio congelados, sin volver a cotizar.

    La fila temporal reproduce la seleccion que ampara el PaymentIntent. Una
    tarifa editada o desactivada despues no cambia lo que el cliente acepto.
    """
    if detalle is None or detalle.numero_personas is None or detalle.precio_calculado is None:
        raise ValueError('El traslado no tiene detalle de precio congelado.')
    demanda = demanda_traslado(detalle, detalle.numero_personas, moneda)
    fila = _TarifaRutaCongelada(
        demanda.tipo_traslado, demanda.zona, demanda.personas, demanda.personas,
        detalle.precio_calculado, demanda.moneda_normalizada,
    )
    return obtener_estrategia_precio('por_ruta').calcular_base(
        {'tarifas_transporte_activas': [fila]}, demanda,
    )


REGISTRO_ESTRATEGIAS_PRECIO: dict[str, EstrategiaPrecio] = {
    TipoEstrategiaPrecio.POR_GRUPO: PorGrupo(),
    TipoEstrategiaPrecio.POR_PERSONA: PorPersona(),
    TipoEstrategiaPrecio.TARIFA_FIJA: TarifaFija(),
    TipoEstrategiaPrecio.POR_NOCHE: PorNoche(),
    TipoEstrategiaPrecio.POR_RUTA: PorRuta(),
}


def registrar_estrategia_precio(clave: str, estrategia: EstrategiaPrecio) -> None:
    """Registra una nueva estrategia de precio."""
    REGISTRO_ESTRATEGIAS_PRECIO[clave] = estrategia


def obtener_estrategia_precio(clave: str = TipoEstrategiaPrecio.POR_GRUPO) -> EstrategiaPrecio:
    """Obtiene la estrategia de precio correspondiente o 'por_grupo' por omision."""
    if clave in REGISTRO_ESTRATEGIAS_PRECIO:
        return REGISTRO_ESTRATEGIAS_PRECIO[clave]
    return REGISTRO_ESTRATEGIAS_PRECIO[TipoEstrategiaPrecio.POR_GRUPO]
