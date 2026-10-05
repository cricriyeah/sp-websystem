import type { ReactNode } from 'react';

/**
 * Envuelve una tarjeta de la columna de pasos. Si va pegada a la anterior (dos
 * respuestas ya dadas seguidas), se sube sobre el hueco de la columna
 * (`gap-6` + 1 px de borde) para que los renglones compartan borde y se lean
 * como un solo bloque compacto. Ver `unidaConAnterior` en `lib/pasos-checkout`.
 */
export function ItemPaso({ unida = false, children }: { unida?: boolean; children: ReactNode }) {
  return <div className={unida ? '-mt-[calc(1.5rem+1px)]' : undefined}>{children}</div>;
}
