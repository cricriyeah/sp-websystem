// El paso del checkout vive en la URL (`?paso=viaje|datos|pago`): cada paso es una entrada
// de historial, así que Atrás vuelve al paso anterior en lugar de salir de la compra.
import { ORDEN_PASOS, type PasoId } from './pasos-checkout';

export function pasoDeQuery(valor: string | null | undefined): PasoId | null {
  return ORDEN_PASOS.find((id) => id === valor) ?? null;
}

export type DecisionPaso =
  | { tipo: 'nada' }
  /** La URL pide un paso al que no se ha llegado, o uno bloqueado: se reescribe al último válido. */
  | { tipo: 'redirigir'; a: PasoId }
  /** La URL pide un paso anterior: se reabre su tarjeta. */
  | { tipo: 'editar'; paso: PasoId }
  /** La URL coincide con el paso actual: ninguna tarjeta queda reabierta. */
  | { tipo: 'cerrarEdicion' };

/**
 * Qué hace el checkout cuando la URL (Atrás, Adelante, recarga) apunta a `urlPaso`.
 * `actual` es el paso más avanzado alcanzado; `bloqueado` es que ya existe un pago en
 * curso y lo anterior no se puede cambiar.
 */
export function decidirPaso(urlPaso: PasoId | null, actual: PasoId, bloqueado: boolean): DecisionPaso {
  const pedido = urlPaso ?? 'viaje';
  const iPedido = ORDEN_PASOS.indexOf(pedido);
  const iActual = ORDEN_PASOS.indexOf(actual);
  if (iPedido > iActual) return { tipo: 'redirigir', a: actual };
  if (iPedido === iActual) return { tipo: 'cerrarEdicion' };
  return bloqueado ? { tipo: 'redirigir', a: actual } : { tipo: 'editar', paso: pedido };
}

/** Misma URL con `?paso=` puesto; conserva el resto del query (moneda, origen…). */
export function conPaso(search: string, paso: PasoId): string {
  const query = new URLSearchParams(search);
  query.set('paso', paso);
  return `?${query.toString()}`;
}
