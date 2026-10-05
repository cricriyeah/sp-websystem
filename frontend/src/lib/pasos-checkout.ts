// Secuencia fija de pasos del checkout, igual para servicio suelto, paquete de
// una empresa y paquete cruza-empresa. Sin React: solo decide qué tarjeta se
// ve y en qué estado, para que los tres checkouts no lo reinventen cada uno.

export type PasoId = 'viaje' | 'contacto' | 'detalles' | 'pago';

export const ORDEN_PASOS: readonly PasoId[] = ['viaje', 'contacto', 'detalles', 'pago'];

export type EstadoTarjeta = 'activo' | 'editando' | 'completado';

/** 1-4, el número que usa el stepper. */
export function numeroDePaso(id: PasoId): number {
  return ORDEN_PASOS.indexOf(id) + 1;
}

/**
 * Estado de la tarjeta de `id` cuando el cliente va en `actual`.
 *
 * - Los pasos posteriores al actual no existen todavía (`'oculto'`).
 * - El actual es el que se está contestando (`'activo'`).
 * - Los anteriores quedan `'completado'` (colapsados a un renglón), salvo el
 *   que el cliente reabrió con "Cambiar" (`editando`), que se ve abierto.
 */
export function estadoDeTarjeta(
  id: PasoId,
  actual: PasoId,
  editando: PasoId | null,
): EstadoTarjeta | 'oculto' {
  const indice = ORDEN_PASOS.indexOf(id);
  const indiceActual = ORDEN_PASOS.indexOf(actual);
  if (indice > indiceActual) return 'oculto';
  if (indice === indiceActual) return 'activo';
  return editando === id ? 'editando' : 'completado';
}

/** `suspendido`: la tarjeta activa mientras el cliente corrige una respuesta anterior. */
export type EstadoVisible = EstadoTarjeta | 'suspendido';

/**
 * Un solo foco abierto a la vez: si el cliente reabrió una respuesta ya dada
 * (`hayEdicion`), la tarjeta activa se pliega a un renglón "pendiente" en vez
 * de quedar abierta debajo. Sus respuestas no se pierden (viven en el estado del
 * pedido) y vuelve a abrirse al terminar la edición.
 */
export function estadoVisible(estado: EstadoTarjeta, hayEdicion: boolean): EstadoVisible {
  return estado === 'activo' && hayEdicion ? 'suspendido' : estado;
}

export type SegmentoPasos<T> =
  | { tipo: 'resumen'; items: T[] }
  | { tipo: 'tarjeta'; item: T };

/**
 * Las respuestas ya dadas que van seguidas forman UNA lista compacta; cualquier
 * otra tarjeta (activa, en edición, suspendida) va aparte, en su sitio. Así tres
 * respuestas cerradas ocupan tres renglones de un mismo bloque en vez de tres
 * tarjetas sueltas que empujan la activa fuera de la pantalla.
 */
export function agruparResumenes<T extends { estado: EstadoVisible }>(items: T[]): SegmentoPasos<T>[] {
  const segmentos: SegmentoPasos<T>[] = [];
  for (const item of items) {
    const ultimo = segmentos[segmentos.length - 1];
    if (item.estado === 'completado') {
      if (ultimo && ultimo.tipo === 'resumen') ultimo.items.push(item);
      else segmentos.push({ tipo: 'resumen', items: [item] });
    } else {
      segmentos.push({ tipo: 'tarjeta', item });
    }
  }
  return segmentos;
}
