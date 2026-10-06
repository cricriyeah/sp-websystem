import type { ReactNode } from 'react';

/**
 * Envuelve una tarjeta de la columna de pasos. Si va junto a otra respuesta ya
 * dada, se sube sobre el hueco de la columna (`gap-6`) hasta dejar solo 8 px:
 * los renglones son tarjetas separadas, delgadas, que se leen como una pila
 * compacta sin llegar a pegarse. Ver `unidaConAnterior` en `lib/pasos-checkout`.
 */
export function ItemPaso({ unida = false, children }: { unida?: boolean; children: ReactNode }) {
  return <div className={unida ? '-mt-4' : undefined}>{children}</div>;
}
