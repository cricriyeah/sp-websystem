'use client';

import type { ReactNode } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';

/**
 * Acciones secundarias del checkout, sin subrayado en reposo.
 *
 * El subrayado le dice al ojo "esto lleva a otra página", y estas acciones
 * abren o cambian algo aquí mismo. Cada rol tiene su pista propia: la flecha
 * en círculo gris de un renglón lo abre (y al abrirse gira), el caret que
 * gira despliega. Se reconocen como clicables por el icono y el cambio de
 * color al pasar el cursor. El subrayado se reserva para los enlaces dentro
 * de una oración (deslinde, términos).
 */

/** El círculo gris con la flecha: la pista de que un renglón se abre (campana-gris del sitio público). */
export const FLECHA = 'inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors group-hover:bg-borde group-focus-visible:bg-borde';

/**
 * «Modificar» de un renglón de respuesta: la etiqueta y una flecha en círculo gris. Es solo la etiqueta:
 * el renglón entero es el botón (`group`), así que el área táctil es todo el renglón.
 */
export function EtiquetaModificar({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-2 texto-etiqueta text-foreground">
      <span className="hidden sm:inline">{children}</span>
      <span className="sr-only sm:hidden">{children}</span>
      <span className={FLECHA}>
        <CaretDown size={16} weight="bold" />
      </span>
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

/** Botón de texto con icono; alto mínimo de 44 px para que se pueda tocar. `neutro` va en `tinta-suave`; `acento`, en café. */
export function AccionTexto({
  onClick, children, icono, abierto, tono = 'neutro', 'aria-controls': ariaControls,
}: AccionTextoProps) {
  return (
    <Button
      variante="texto"
      className={tono === 'neutro' ? 'text-tinta-suave' : undefined}
      onClick={onClick}
      aria-expanded={abierto}
      aria-controls={ariaControls}
    >
      {icono}
      <span>{children}</span>
      {abierto !== undefined && (
        <CaretDown size={12} weight="bold" className={`transition-transform duration-[var(--duracion-media)] ${abierto ? 'rotate-180' : ''}`} />
      )}
    </Button>
  );
}
