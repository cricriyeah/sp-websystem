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

/**
 * ¿Esta tarjeta va pegada a la anterior? Dos respuestas ya dadas seguidas se
 * ven como UN bloque compacto (renglones que comparten borde) y no como
 * tarjetas sueltas separadas por huecos: tres respuestas cerradas dejan de
 * empujar la tarjeta activa fuera de la pantalla. Cualquier otra tarjeta
 * (activa, en edición, suspendida) conserva su separación normal.
 *
 * Se resuelve por posición y no reubicando las tarjetas en otro contenedor:
 * así cada una sigue montada y su colapso sigue animándose.
 */
export function unidaConAnterior(estados: readonly EstadoVisible[], indice: number): boolean {
  return indice > 0 && estados[indice] === 'completado' && estados[indice - 1] === 'completado';
}
