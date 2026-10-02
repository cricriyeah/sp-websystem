import type { Moneda, PaqueteCatalogo } from './api';
import { calcularBasePaquete } from './precio-paquete';
import {
  totalPersonalizaciones,
  type PersonalizacionUI,
  type SeleccionPersonalizacion,
} from './personalizaciones';

export type PersonalizacionSeleccionada = SeleccionPersonalizacion;

export type CalculoPrecioPaquete = {
  precioAncla: number | null;
  totalPersonalizaciones: number | null;
  precioFinal: number | null;
  moneda: Moneda;
  serviciosActivosCount: number;
};

/**
 * Calcula de forma reactiva en cliente el precio del paquete.
 *
 * Fórmula:
 *     paquete.precio_total_en(moneda, personas)                               # base del grupo
 *   + Σ  sp.precio_en(moneda) de las personalizaciones explícitamente seleccionadas
 *
 * Cada personalización check que cobrar_por_persona se multiplica por personas.
 * Los inputs son siempre gratis. Si falta un precio, devuelve null.
 */
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  moneda?: Moneda,
): CalculoPrecioPaquete;
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  personalizacionesOpcionales?: PersonalizacionSeleccionada[],
  personas?: number,
  moneda?: Moneda,
): CalculoPrecioPaquete;
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  personalizacionesOMoneda?: PersonalizacionSeleccionada[] | Moneda,
  personasArg: number = 1,
  monedaArg: Moneda = 'MXN',
): CalculoPrecioPaquete {
  let personalizacionesOpcionales: PersonalizacionSeleccionada[] = [];
  let personas = personasArg;
  let moneda: Moneda = monedaArg;

  if (typeof personalizacionesOMoneda === 'string') {
    moneda = personalizacionesOMoneda;
    personalizacionesOpcionales = [];
    personas = 1;
  } else if (Array.isArray(personalizacionesOMoneda)) {
    personalizacionesOpcionales = personalizacionesOMoneda;
  }

  const precioAncla = calcularBasePaquete(paquete, moneda, personas);

  const catalogoMap = new Map<number, PersonalizacionUI>();
  for (const item of paquete.servicios_asociados || []) {
    for (const sp of item.servicio?.personalizaciones || []) {
      if (!catalogoMap.has(sp.id)) {
        catalogoMap.set(sp.id, sp);
      }
    }
  }
  const catalogo = Array.from(catalogoMap.values());

  const totalPers = totalPersonalizaciones(
    catalogo,
    personalizacionesOpcionales,
    personas,
    moneda,
    paquete.tipo_cambio_usd,
  );

  const precioFinal =
    precioAncla === null || totalPers === null
      ? null
      : Math.max(0, Math.round((precioAncla + totalPers) * 100) / 100);

  return {
    precioAncla,
    totalPersonalizaciones: totalPers,
    precioFinal,
    moneda,
    serviciosActivosCount: paquete.servicios_asociados?.length ?? 0,
  };
}

/**
 * Formatea un número como moneda (MXN o USD).
 */
export function formatearPrecio(monto: number | null, moneda: Moneda = 'MXN'): string {
  if (monto === null || !Number.isFinite(monto)) return '—';
  return new Intl.NumberFormat(moneda === 'USD' ? 'en-US' : 'es-MX', {
    style: 'currency',
    currency: moneda,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(monto);
}
