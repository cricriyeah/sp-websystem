'use client';

import { useId, type ComponentProps, type ReactNode } from 'react';
import { Check } from '@phosphor-icons/react/ssr';
import { cn } from './cn';

type CheckboxProps = Omit<ComponentProps<'input'>, 'type' | 'children'> & {
  /** Texto de la casilla, a la derecha y clicable. */
  etiqueta: ReactNode;
};

/**
 * Casilla de 24 con área táctil de 48, radio `casilla`; marcada = relleno `cafe` con
 * palomita blanca. El `<input>` nativo es el que se toca (48 × 48, invisible) y el
 * cuadro de 24 es solo su dibujo, así el formulario, el teclado y el lector de
 * pantalla ven una casilla de verdad. Isla cliente por `useId()` (enlaza etiqueta y
 * control). Foco con el anillo `ring`.
 */
export function Checkbox({ etiqueta, id, className, ...props }: CheckboxProps) {
  const generado = useId();
  const idControl = id ?? generado;

  return (
    <div className={cn('flex items-center', className)}>
      <span className="relative inline-flex size-12 shrink-0 items-center justify-center">
        <input
          {...props}
          id={idControl}
          type="checkbox"
          className="peer absolute inset-0 size-full cursor-pointer appearance-none opacity-0 disabled:cursor-not-allowed"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none inline-flex size-6 items-center justify-center rounded-casilla border border-borde-control bg-superficie text-blanco transition-colors peer-checked:border-cafe peer-checked:bg-cafe peer-checked:[&>svg]:opacity-100 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring peer-disabled:opacity-60"
        >
          <Check size={16} weight="bold" className="opacity-0 transition-opacity" />
        </span>
      </span>
      <label htmlFor={idControl} className="texto-cuerpo flex min-h-12 flex-1 cursor-pointer items-center py-2 text-foreground">
        {etiqueta}
      </label>
    </div>
  );
}
