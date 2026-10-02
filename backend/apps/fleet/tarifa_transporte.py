"""Resolución de la fila de TransporteTarifa que aplica a una demanda concreta.
Función pura sobre un queryset ya scopeado por RLS; no calcula dinero (eso es
estrategias_precio.PorRuta), solo elige la fila."""


class TarifaTransporteNoConfigurada(Exception):
    pass


def resolver_tarifa_transporte(tarifas, *, tipo_traslado, zona, personas):
    """`tarifas`: iterable de TransporteTarifa (ya filtrado por empresa+activo).
    Devuelve la fila cuyo tipo/zona coinciden y cuyo rango
    [personas_min, personas_max] contiene `personas`. Lanza
    TarifaTransporteNoConfigurada si no hay ninguna."""
    zona_norm = zona or ''
    for t in tarifas:
        if t.tipo_traslado != tipo_traslado:
            continue
        if t.zona != zona_norm:
            continue
        if personas < t.personas_min:
            continue
        if t.personas_max is not None and personas > t.personas_max:
            continue
        return t
    raise TarifaTransporteNoConfigurada(
        f'No hay tarifa de transporte para tipo={tipo_traslado} zona={zona_norm!r} personas={personas}.'
    )


def peor_tarifa(tarifas, *, personas, moneda, tipo_cambio=None):
    """La tarifa más alta que puede tocarle a un grupo de `personas` (cualquier tipo
    y zona), en `moneda`, o None si ninguna aplica o no tiene precio en esa moneda.

    El precio de un paquete debe cubrirla: el cliente elige el tipo de traslado al
    reservar, así que hay que asumir el más caro."""
    precios = []
    for t in tarifas:
        if personas < t.personas_min:
            continue
        if t.personas_max is not None and personas > t.personas_max:
            continue
        precios.append(t.precio_en(moneda, tipo_cambio))
    return max(precios) if precios else None
