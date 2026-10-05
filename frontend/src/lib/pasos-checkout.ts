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
