import type { ReactNode } from 'react';

/**
 * La pregunta encima de la caja de un campo compacto (selector, hotel, personas), igual que en los campos de
 * contacto: la etiqueta va fuera y la caja queda con una sola línea. `children` es la caja.
 * Server Component.
 */
export function CampoEtiquetado({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-base text-foreground sm:text-sm">{label}</span>
      {children}
    </div>
  );
}
