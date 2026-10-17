import type { ComponentProps } from 'react';
import { cn } from './cn';
import { CAJA_CAMPO, CAJA_CAMPO_ERROR } from './caja-campo';

type InputProps = ComponentProps<'input'> & {
  /** Pinta el borde de error y marca `aria-invalid`. Sin él, se respeta un `aria-invalid` pasado a mano. */
  invalido?: boolean;
};

/**
 * Campo de texto de una línea. Servible desde servidor. 16 px mínimo (`text-base`)
 * para que iOS no haga zoom al enfocarlo. Va dentro de `Field`, que le pone `id`,
 * `aria-describedby` y `aria-invalid`; solo, necesita su propia etiqueta.
 */
export function Input({ invalido, type = 'text', className, ...props }: InputProps) {
  const ariaInvalido = props['aria-invalid'];
  const malo = invalido ?? (ariaInvalido === true || ariaInvalido === 'true');

  return (
    <input
      {...props}
      type={type}
      aria-invalid={malo || undefined}
      className={cn(
        malo ? CAJA_CAMPO_ERROR : CAJA_CAMPO,
        'min-h-12 w-full px-4 py-3 text-base text-foreground outline-none placeholder:text-apagado',
        malo ? 'focus:border-error' : 'focus:border-accent',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        'disabled:cursor-not-allowed disabled:bg-cafe-bruma disabled:text-apagado',
        className,
      )}
    />
  );
}
