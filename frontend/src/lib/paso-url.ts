// El paso del checkout vive en la URL (`?paso=viaje|datos|pago`): cada paso es una entrada
// de historial, así que Atrás vuelve al paso anterior en lugar de salir de la compra.
import { ORDEN_PASOS, type PasoId } from './pasos-checkout';
import { estaAntesDe, pasoDeLaPantalla, type Pantalla } from './pantallas-checkout';

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

// Asistente móvil: además del paso, la URL lleva la pantalla (`?paso=datos&pantalla=recogida`).
// Cada pantalla es una entrada de historial; `?paso=` se sigue escribiendo para que el borrador
// se reponga igual y para que al ensanchar la ventana las tarjetas abran el paso correcto.

export function pantallaDeQuery(valor: string | null | undefined): string | null {
  return valor || null;
}

/** Misma URL con `?paso=` y `?pantalla=` de `id`; conserva el resto del query. */
export function conPantalla(search: string, pantallas: readonly Pantalla[], id: string): string {
  const query = new URLSearchParams(search);
  query.set('paso', pasoDeLaPantalla(pantallas, id));
  query.set('pantalla', id);
  return `?${query.toString()}`;
}

export type DecisionPantalla =
  | { tipo: 'nada' }
  | { tipo: 'mostrar'; id: string }
  /** La URL pide una pantalla a la que no se ha llegado, que no existe o bloqueada. */
  | { tipo: 'redirigir'; a: string };

/**
 * Qué hace el asistente cuando la URL (Atrás, Adelante, recarga) apunta a `urlId`.
 * `alcanzada` es la pantalla más avanzada a la que llegó el cliente; `minima`, si hay un pago
 * en curso, la primera a la que todavía se puede volver.
 */
export function decidirPantalla(
  urlId: string | null,
  pantallas: readonly Pantalla[],
  alcanzada: string,
  minima: string | null,
): DecisionPantalla {
  if (urlId === null) return { tipo: 'nada' };
  const existe = pantallas.some((x) => x.id === urlId);
  if (!existe || estaAntesDe(pantallas, alcanzada, urlId)) return { tipo: 'redirigir', a: alcanzada };
  if (minima && estaAntesDe(pantallas, urlId, minima)) return { tipo: 'redirigir', a: minima };
  return { tipo: 'mostrar', id: urlId };
}
