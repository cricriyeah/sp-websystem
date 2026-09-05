"""Definición de clases y contratos de estrategias de cupo (ADR-003)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from django.core.exceptions import ValidationError

from .nucleo import (
    MODO_COMPARTIDO,
    MODO_EXCLUSIVO,
    MOTIVO_LLENO,
    MOTIVO_SIN_LUGAR,
    MOTIVO_SIN_PANGA,
    motivo_sin_lugar,
    ocupacion_por_rango,
    recursos_disponibles_en_rango,
)


class ModoOcupacion(StrEnum):
    """Eje de modo de ocupación de recursos (corrección 8 del diseño)."""
    EXCLUSIVO = MODO_EXCLUSIVO
    COMPARTIDO = MODO_COMPARTIDO


@dataclass(frozen=True)
class DemandaCupo:
    """Solicitud de cupo para una fecha (o rango) y número de personas."""
    fecha: date
    personas: int
    modo: ModoOcupacion = ModoOcupacion.EXCLUSIVO
    excluir_pk: int | None = None
    fecha_fin: date | None = None
    cantidad_recursos: int = 1

    @property
    def noches(self) -> int:
        if self.fecha_fin and self.fecha_fin > self.fecha:
            return (self.fecha_fin - self.fecha).days
        return 1

    @property
    def fecha_salida(self) -> date:
        if self.fecha_fin:
            return self.fecha_fin
        from datetime import timedelta
        return self.fecha + timedelta(days=1)


@dataclass(frozen=True)
class ResultadoDisponibilidad:
    """Resultado de la consulta de disponibilidad."""
    disponible: bool
    motivo: str | None = None


class EstrategiaCupo(ABC):
    """Clase base abstracta para estrategias tipadas de cupo y disponibilidad."""

    @abstractmethod
    def evaluar(
        self,
        demanda: DemandaCupo,
        grupos: list[int],
        capacidades: list[int],
        tope: int,
    ) -> ResultadoDisponibilidad:
        """Evalúa si la demanda cabe en la fecha solicitada.

        Devuelve un ResultadoDisponibilidad sin lanzar excepciones.
        """
        pass

    def validar(
        self,
        demanda: DemandaCupo,
        grupos: list[int],
        capacidades: list[int],
        tope: int,
    ) -> None:
        """Valida que haya cupo disponible. Lanza ValidationError si no cabe."""
        resultado = self.evaluar(demanda, grupos, capacidades, tope)
        if resultado.disponible:
            return

        if resultado.motivo == MOTIVO_LLENO:
            raise ValidationError(
                f'No hay cupo disponible para el {demanda.fecha}: se alcanzo el maximo de viajes del dia.'
            )
        if resultado.motivo == MOTIVO_SIN_PANGA:
            raise ValidationError(
                f'No queda panga para un grupo de {demanda.personas} personas el {demanda.fecha}. '
                f'Las de mayor capacidad ya estan comprometidas.'
            )
        if resultado.motivo == MOTIVO_SIN_LUGAR:
            raise ValidationError(
                f'No hay espacio disponible para {demanda.personas} personas el {demanda.fecha}.'
            )
        raise ValidationError(f'No hay cupo disponible para el {demanda.fecha}.')

    @abstractmethod
    def evaluar_rango(
        self,
        fechas: list[date],
        grupos_por_fecha: dict[date, list[int]],
        capacidades_por_fecha: dict[date, list[int]],
        topes_por_fecha: dict[date, int],
        personas: int,
        modo: ModoOcupacion | None = None,
    ) -> dict[date, ResultadoDisponibilidad]:
        """Evalúa la disponibilidad a lo largo de un rango de fechas."""
        pass


class PorRecursoDia(EstrategiaCupo):
    """Estrategia de ocupación de recurso por rango de 1 día (paseos y transporte).

    Implementación de referencia para pesca y paseos diarios basados en embarcación.
    Soporta modo exclusivo (emparejamiento por tamaño) y modo compartido (suma de personas).
    """

    def __init__(self, modo: ModoOcupacion = ModoOcupacion.EXCLUSIVO):
        self.modo_predeterminado = modo

    def evaluar(
        self,
        demanda: DemandaCupo,
        grupos: list[int],
        capacidades: list[int],
        tope: int,
    ) -> ResultadoDisponibilidad:
        modo = demanda.modo if demanda.modo is not None else self.modo_predeterminado
        motivo = motivo_sin_lugar(
            personas=demanda.personas,
            grupos=grupos,
            capacidades=capacidades,
            tope=tope,
            modo=modo,
        )
        return ResultadoDisponibilidad(disponible=(motivo is None), motivo=motivo)

    def evaluar_rango(
        self,
        fechas: list[date],
        grupos_por_fecha: dict[date, list[int]],
        capacidades_por_fecha: dict[date, list[int]],
        topes_por_fecha: dict[date, int],
        personas: int,
        modo: ModoOcupacion | None = None,
    ) -> dict[date, ResultadoDisponibilidad]:
        modo_activo = modo or self.modo_predeterminado
        motivos = ocupacion_por_rango(
            fechas=fechas,
            grupos_por_fecha=grupos_por_fecha,
            capacidades_por_fecha=capacidades_por_fecha,
            topes_por_fecha=topes_por_fecha,
            personas=personas,
            modo=modo_activo,
        )
        return {
            fecha: ResultadoDisponibilidad(disponible=(motivo is None), motivo=motivo)
            for fecha, motivo in motivos.items()
        }


class PorNoche(EstrategiaCupo):
    """Estrategia de ocupación de recursos por rango de noches (hospedaje).

    Traslape semi-abierto [check-in, check-out) donde el día de salida queda
    libre para nuevo check-in esa misma tarde.
    Soporta que una reserva ocupe 1..N habitaciones (cantidad_recursos).
    """

    def evaluar(
        self,
        demanda: DemandaCupo,
        grupos: list[int],
        capacidades: list[int],
        tope: int,
    ) -> ResultadoDisponibilidad:
        req_recursos = max(1, demanda.cantidad_recursos)
        recursos_disponibles = max(0, len(capacidades) - len(grupos))
        if recursos_disponibles < req_recursos:
            return ResultadoDisponibilidad(disponible=False, motivo=MOTIVO_SIN_LUGAR)

        caps_libres = sorted(capacidades[len(grupos):], reverse=True)
        if sum(caps_libres[:req_recursos]) < demanda.personas:
            return ResultadoDisponibilidad(disponible=False, motivo=MOTIVO_SIN_LUGAR)

        return ResultadoDisponibilidad(disponible=True)

    def evaluar_ocupacion(
        self,
        demanda: DemandaCupo,
        recursos_con_ocupaciones: list[tuple[int, int, list[tuple[date, date]]]],
        tope: int | None = None,
    ) -> ResultadoDisponibilidad:
        """Evalúa disponibilidad contra las ocupaciones exactas por recurso en el rango de fechas."""
        ini = demanda.fecha
        fin = demanda.fecha_salida
        req_recursos = max(1, demanda.cantidad_recursos)

        libres = recursos_disponibles_en_rango(recursos_con_ocupaciones, ini, fin)
        if len(libres) < req_recursos:
            return ResultadoDisponibilidad(disponible=False, motivo=MOTIVO_SIN_LUGAR)

        caps_libres = sorted((cap for _, cap in libres), reverse=True)
        if sum(caps_libres[:req_recursos]) < demanda.personas:
            return ResultadoDisponibilidad(disponible=False, motivo=MOTIVO_SIN_LUGAR)

        return ResultadoDisponibilidad(disponible=True)

    def evaluar_rango(
        self,
        fechas: list[date],
        grupos_por_fecha: dict[date, list[int]],
        capacidades_por_fecha: dict[date, list[int]],
        topes_por_fecha: dict[date, int],
        personas: int,
        modo: ModoOcupacion | None = None,
    ) -> dict[date, ResultadoDisponibilidad]:
        resultado = {}
        for fecha in fechas:
            demanda = DemandaCupo(fecha=fecha, personas=personas)
            resultado[fecha] = self.evaluar(
                demanda=demanda,
                grupos=grupos_por_fecha.get(fecha, []),
                capacidades=capacidades_por_fecha.get(fecha, []),
                tope=topes_por_fecha.get(fecha, 0),
            )
        return resultado


class BajoDemanda(EstrategiaCupo):
    """Estrategia de cupo para servicios sin inventario rígido que se agote (chef, guías, masajes).

    Siempre disponible, o con tope suave opcional si se configura.
    """

    def evaluar(
        self,
        demanda: DemandaCupo,
        grupos: list[int],
        capacidades: list[int],
        tope: int,
    ) -> ResultadoDisponibilidad:
        if tope is not None and tope > 0 and len(grupos) + 1 > tope:
            return ResultadoDisponibilidad(disponible=False, motivo=MOTIVO_LLENO)
        return ResultadoDisponibilidad(disponible=True)

    def evaluar_rango(
        self,
        fechas: list[date],
        grupos_por_fecha: dict[date, list[int]],
        capacidades_por_fecha: dict[date, list[int]],
        topes_por_fecha: dict[date, int],
        personas: int,
        modo: ModoOcupacion | None = None,
    ) -> dict[date, ResultadoDisponibilidad]:
        return {
            fecha: ResultadoDisponibilidad(disponible=True)
            for fecha in fechas
        }
