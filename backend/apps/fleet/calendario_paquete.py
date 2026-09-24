"""Aritmética de fechas de un paquete. Función pura: sin base de datos.

Es la única fuente de esta regla (backend y frontend la replican con el mismo
vector de prueba, ver spec §5 y §7). `dia_estancia` cuenta desde 1 (día de llegada)."""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ComponenteCalendario:
    dia_estancia: int
    estrategia_cupo: str
    noches: int | None


def noches_del_paquete(componentes) -> int | None:
    for c in componentes:
        if c.estrategia_cupo == 'por_noche':
            return c.noches
    return None


def fecha_de_componente(inicio: date, dia_estancia: int) -> date:
    return inicio + timedelta(days=dia_estancia - 1)


def fecha_salida(inicio: date, componentes) -> date | None:
    """Salida del hospedaje: inicio + noches. None si el paquete no incluye hospedaje."""
    noches = noches_del_paquete(componentes)
    return inicio + timedelta(days=noches) if noches else None


def fecha_ancla(inicio: date, componentes) -> date:
    """Día de la actividad operativa (por_recurso_dia); sin actividad, el inicio.

    Es el valor de `Reserva.fecha` en un paquete de una sola empresa: el motor de
    cupo, la agenda y la regla de una salida por día leen ese campo."""
    for c in componentes:
        if c.estrategia_cupo == 'por_recurso_dia':
            return fecha_de_componente(inicio, c.dia_estancia)
    return inicio


def inicio_desde_reserva(fecha: date, fecha_salida_reserva: date | None, componentes) -> date:
    """Recupera el inicio del paquete a partir de una Reserva ya guardada."""
    noches = noches_del_paquete(componentes)
    if fecha_salida_reserva and noches:
        return fecha_salida_reserva - timedelta(days=noches)
    return fecha
