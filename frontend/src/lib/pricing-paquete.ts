import type { Moneda, PaqueteCatalogo } from './api';

export type CalculoPrecioPaquete = {
  precioAncla: number;
  totalAjustesDescontados: number;
  precioFinal: number;
  moneda: Moneda;
  serviciosActivosCount: number;
};

/**
 * Calcula de forma reactiva en cliente el precio ancla del paquete
 * aplicando los descuentos de los servicios removibles que el usuario desmarcó.
 *
 * Perception-First Design: El precio ancla no es una suma de partes con descuento;
 * arranca en el valor total de la experiencia empaquetada y descuenta
 * el ajuste individual de cada servicio removido sin perder su anclaje perceptivo.
 */
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  serviciosExcluidosIds: number[],
  moneda: Moneda = 'MXN',
): CalculoPrecioPaquete {
  const anclaRaw =
    moneda === 'USD' && paquete.precio_ancla_usd
      ? paquete.precio_ancla_usd
      : paquete.precio_ancla;
  const precioAncla = parseFloat(anclaRaw) || 0;

  let totalAjustesDescontados = 0;
  let serviciosActivosCount = 0;

  for (const item of paquete.servicios_asociados) {
    const sId = item.servicio?.id ?? item.servicio_id;
    const estaExcluido = serviciosExcluidosIds.includes(sId);

    if (estaExcluido && item.removible) {
      const ajusteRaw =
        moneda === 'USD' && item.ajuste_precio_usd
          ? item.ajuste_precio_usd
          : item.ajuste_precio;
      const ajuste = parseFloat(ajusteRaw) || 0;
      totalAjustesDescontados += ajuste;
    } else {
      serviciosActivosCount += 1;
    }
  }

  const precioFinal = Math.max(0, precioAncla - totalAjustesDescontados);

  return {
    precioAncla,
    totalAjustesDescontados,
    precioFinal,
    moneda,
    serviciosActivosCount,
  };
}

/**
 * Formatea un número como moneda (MXN o USD).
 */
export function formatearPrecio(monto: number, moneda: Moneda = 'MXN'): string {
  return new Intl.NumberFormat(moneda === 'USD' ? 'en-US' : 'es-MX', {
    style: 'currency',
    currency: moneda,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(monto);
}
