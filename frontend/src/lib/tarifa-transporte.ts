import type { Moneda, TipoTraslado, TrasladosCatalogo, Zona } from './api';

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

export function precioTarifa(tarifa: Tarifa, moneda: Moneda): number | null {
  const crudo = moneda === 'USD' ? tarifa.precio_usd : tarifa.precio;
  if (crudo === null || crudo === undefined || !Number.isFinite(Number(crudo))) return null;
  return Number(crudo);
}
