import type { Moneda, TipoTraslado, TrasladosCatalogo, Zona } from './api';
import { aMoneda } from './moneda';

export type Tarifa = TrasladosCatalogo['tarifas'][number];

/** Espejo de backend/apps/fleet/tarifa_transporte.py::resolver_tarifa_transporte. */
export function resolverTarifa(
  tarifas: Tarifa[],
  tipo: TipoTraslado,
  zona: Zona | '',
  personas: number,
): Tarifa | null {
  return (
    tarifas.find(
      (t) =>
        t.tipo_traslado === tipo &&
        t.zona === (zona || '') &&
        personas >= t.personas_min &&
        (t.personas_max === null || personas <= t.personas_max),
    ) ?? null
  );
}

export function precioTarifa(tarifa: Tarifa, moneda: Moneda, tipoCambio: string): number | null {
  return aMoneda(tarifa.precio, moneda, tipoCambio);
}
