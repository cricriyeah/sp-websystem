/**
 * La nota que el cliente deja en el checkout para quien lo lleva. Espejo del backend
 * (`bookings.models.NOTAS_CLIENTE_MAX`): si cambia allá, cambia aquí.
 */
export const NOTAS_MAX = 500;

/** Lo que viaja al backend: sin espacios de sobra y nunca más largo que el tope. */
export function notasParaEnviar(notas: string): string {
  return notas.trim().slice(0, NOTAS_MAX);
}
