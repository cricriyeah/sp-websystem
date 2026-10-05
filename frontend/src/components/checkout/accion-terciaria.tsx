'use client';

import type { ReactNode } from 'react';
import { CaretDown, PencilSimple } from '@phosphor-icons/react';

/**
 * Acciones secundarias del checkout, sin subrayado en reposo.
 *
 * El subrayado le dice al ojo "esto lleva a otra página", y estas acciones
 * abren o cambian algo aquí mismo. Cada rol tiene su pista propia: el lápiz
 * edita, el caret que gira despliega. Quedan por debajo del CTA amarillo en
 * contraste pero se reconocen como clicables por el icono, el cambio de color
 * al pasar el cursor y el subrayado que aparece al enfocar con teclado. El
 * subrayado se reserva para los enlaces dentro de una oración (deslinde,
 * términos).
 */

/**
 * "Modificar" de un renglón de respuesta. Es solo la etiqueta: el renglón
 * entero es el botón (`group`), así que el área táctil es todo el renglón.
 */
export function EtiquetaModificar({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-muted transition-colors group-hover:text-foreground group-hover:underline group-hover:underline-offset-4 group-focus-visible:text-foreground group-focus-visible:underline group-focus-visible:underline-offset-4">
      <PencilSimple size={13} />
      {children}
    </span>
  );
}

type AccionTextoProps = {
  onClick: () => void;
  children: ReactNode;
  icono?: ReactNode;
  /** Si se pasa (true/false) el control es un despliegue: muestra un caret que gira. */
  abierto?: boolean;
  /** `acento` para "revelar más"; `neutro` para volver o cambiar de modo. */
  tono?: 'acento' | 'neutro';
  'aria-controls'?: string;
};

/** Botón de texto con icono; alto mínimo de 40 px para que se pueda tocar. */
export function AccionTexto({
  onClick, children, icono, abierto, tono = 'neutro', 'aria-controls': ariaControls,
}: AccionTextoProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={abierto}
      aria-controls={ariaControls}
      className={`inline-flex min-h-10 items-center gap-1.5 self-start text-xs font-medium transition-colors hover:text-foreground focus-visible:underline focus-visible:underline-offset-4 ${
        tono === 'acento' ? 'text-accent' : 'text-muted'
      }`}
    >
      {icono}
      <span>{children}</span>
      {abierto !== undefined && (
        <CaretDown size={12} weight="bold" className={`transition-transform duration-300 ${abierto ? 'rotate-180' : ''}`} />
      )}
    </button>
  );
}
