// Validación «con dueño»: cada problema dice a qué paso y a qué campo pertenece, para que el
// aviso lleve al cliente allí en vez de dejarlo en Pago con un error que no sabe dónde corregir.
import { ORDEN_PASOS, type PasoId } from './pasos-checkout';

export type Problema = {
  paso: PasoId;
  /** Id del control (o de su error, que el control referencia con `aria-describedby`); vacío si no hay control. */
  campo: string;
  mensaje: string;
};

/**
 * El primer problema del flujo: gana el paso más temprano y, dentro de él, el primero de la
 * lista. `null` si todo está en orden. Los `null` de la entrada (validaciones que pasaron) se ignoran.
 */
export function validarTodo(problemas: ReadonlyArray<Problema | null>): Problema | null {
  let primero: Problema | null = null;
  for (const problema of problemas) {
    if (!problema) continue;
    if (!primero || ORDEN_PASOS.indexOf(problema.paso) < ORDEN_PASOS.indexOf(primero.paso)) primero = problema;
  }
  return primero;
}
