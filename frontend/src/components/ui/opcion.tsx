'use client';

import { useId, type ComponentProps, type ReactNode } from 'react';
import { cn } from './cn';

type OpcionProps = Omit<ComponentProps<'input'>, 'type' | 'children'> & {
  /** Texto de la opción, a la derecha y clicable. */
  etiqueta: ReactNode;
};

/**
 * Opción de radio: círculo de 24 con área táctil de 48; marcada = borde y punto
 * `cafe`. Igual que `Checkbox`: el `<input type="radio">` nativo es el control
 * (48 × 48, invisible) y el círculo es su dibujo, por lo que `name`, las flechas del
 * teclado y el lector de pantalla funcionan solos. Agrúpalas con `name` común dentro
 * de un `<fieldset>` con `<legend>`. Isla cliente por `useId()`. Foco con `ring`.
 */
export function Opcion({ etiqueta, id, className, ...props }: OpcionProps) {
  const generado = useId();
  const idControl = id ?? generado;

  return (
    <div className={cn('flex items-center', className)}>
      <span className="relative inline-flex size-12 shrink-0 items-center justify-center">
        <input
          {...props}
          id={idControl}
          type="radio"
          className="peer absolute inset-0 size-full cursor-pointer appearance-none opacity-0 disabled:cursor-not-allowed"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none relative inline-flex size-6 rounded-full border border-borde-control bg-superficie transition-colors after:absolute after:inset-1.5 after:scale-0 after:rounded-full after:bg-cafe after:transition-transform peer-checked:border-cafe peer-checked:after:scale-100 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring peer-disabled:opacity-60"
        />
      </span>
      <label htmlFor={idControl} className="texto-cuerpo flex min-h-12 flex-1 cursor-pointer items-center py-2 text-foreground">
        {etiqueta}
      </label>
    </div>
  );
}
