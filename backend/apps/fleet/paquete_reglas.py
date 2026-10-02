"""Reglas de coherencia de un Paquete, en función pura.

Una sola función valida un paquete completo a partir de datos simples, para que la
usen igual el formset del admin, `Paquete.validar_configuracion()` y las pruebas.
No toca la base de datos ni importa modelos."""
from dataclasses import dataclass

POR_NOCHE = 'por_noche'
POR_RECURSO_DIA = 'por_recurso_dia'


@dataclass(frozen=True)
class Componente:
    servicio_nombre: str
    empresa_id: int
    estrategia_cupo: str
    noches: int | None
    dia_estancia: int
    personas_incluidas: int
    # None = no se valida aquí (el hospedaje depende de las habitaciones reales).
    tope_personas: int | None
    salidas: int = 1


def hay_conflicto_anticipo(*, permite_anticipo: bool, empresas_ids: set[int]) -> bool:
    """Un paquete con servicios de dos empresas no puede tener anticipo."""
    return bool(permite_anticipo) and len(empresas_ids) > 1


def errores_de_paquete(*, permite_anticipo: bool, componentes: list[Componente]) -> list[str]:
    errores: list[str] = []
    empresas = {c.empresa_id for c in componentes}

    if hay_conflicto_anticipo(permite_anticipo=permite_anticipo, empresas_ids=empresas):
        errores.append(
            'Un paquete con servicios de dos empresas no admite anticipo: desactiva "permite anticipo".'
        )
    if len(empresas) > 1 and len(empresas) != len(componentes):
        errores.append('En un paquete de dos empresas solo puede haber un servicio por empresa.')

    hospedajes = [c for c in componentes if c.estrategia_cupo == POR_NOCHE]
    if len(hospedajes) > 1:
        errores.append('Un paquete solo puede incluir un hospedaje.')

    for c in componentes:
        if c.estrategia_cupo == POR_NOCHE:
            if not c.noches or c.noches < 1:
                errores.append(f'"{c.servicio_nombre}": indica cuántas noches incluye el paquete.')
            if c.dia_estancia != 1:
                errores.append(f'"{c.servicio_nombre}": el hospedaje empieza el día 1 del paquete.')
        elif c.noches is not None:
            errores.append(f'"{c.servicio_nombre}": las noches solo aplican al hospedaje.')

        if c.salidas < 1:
            errores.append(f'"{c.servicio_nombre}": las salidas deben ser al menos 1.')
        elif c.salidas > 1 and c.estrategia_cupo != POR_RECURSO_DIA:
            errores.append(f'"{c.servicio_nombre}": las salidas solo aplican a actividades.')

        if c.dia_estancia < 1:
            errores.append(f'"{c.servicio_nombre}": el día del paquete debe ser 1 o mayor.')

        if c.personas_incluidas < 1:
            errores.append(f'"{c.servicio_nombre}": las personas incluidas deben ser al menos 1.')
        elif c.tope_personas is not None and c.personas_incluidas > c.tope_personas:
            errores.append(
                f'"{c.servicio_nombre}": las personas incluidas ({c.personas_incluidas}) '
                f'superan el máximo del servicio ({c.tope_personas}).'
            )

    noches_paquete = hospedajes[0].noches if hospedajes and hospedajes[0].noches else None
    for c in componentes:
        if c.estrategia_cupo == POR_NOCHE or c.dia_estancia < 1:
            continue
        ultimo_dia = c.dia_estancia + max(1, c.salidas) - 1
        if noches_paquete is None and ultimo_dia != 1:
            errores.append(
                f'"{c.servicio_nombre}": sin hospedaje el paquete dura un día; el servicio debe caer el día 1.'
            )
        elif noches_paquete is not None and ultimo_dia > noches_paquete:
            errores.append(
                f'"{c.servicio_nombre}": el día {ultimo_dia} cae fuera de la estancia '
                f'({noches_paquete} noche(s); el último día válido es el {noches_paquete}).'
            )

    dias_actividad = {
        (c.dia_estancia, max(1, c.salidas)) for c in componentes if c.estrategia_cupo == POR_RECURSO_DIA
    }
    if len(dias_actividad) > 1:
        errores.append(
            'Las actividades del paquete deben ocurrir los mismos días de la estancia '
            '(mismo día de inicio y mismo número de salidas).'
        )

    actividades = [c for c in componentes if c.estrategia_cupo == POR_RECURSO_DIA]
    if len(actividades) > 1 and any(c.salidas > 1 for c in actividades):
        errores.append(
            'Una actividad de varios días no puede acompañarse de otra actividad de mar en el mismo paquete.'
        )

    if len(empresas) > 1 and any(c.salidas > 1 for c in componentes):
        errores.append('Una actividad de varios días solo se admite en un paquete de una sola empresa.')

    return errores
