import type { ComponentProps } from 'react';
import { cn } from './cn';
import { CAJA_CAMPO } from './caja-campo';

/**
 * Campo de varias líneas, con la caja de `Input` (`ui/caja-campo.ts`): mismo borde, foco y tamaño de letra (16 px,
 * sin zoom en iOS). Crece con la mano del cliente solo hacia abajo. Solo necesita su propia etiqueta.
 */
export function AreaTexto({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      {...props}
      className={cn(CAJA_CAMPO, 'block w-full resize-y py-3 leading-snug outline-none disabled:cursor-not-allowed', className)}
    />
  );
}
