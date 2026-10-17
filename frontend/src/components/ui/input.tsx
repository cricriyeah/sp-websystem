import type { ComponentProps } from 'react';
import { cn } from './cn';
import { CAJA_CAMPO, CAJA_CAMPO_ERROR } from './caja-campo';

type InputProps = ComponentProps<'input'> & {
  /** Pinta el borde de error y marca `aria-invalid`. Sin él, se respeta un `aria-invalid` pasado a mano. */
  invalido?: boolean;
  /**
   * `heredado`: sin el aspecto de la marca; todo llega por `className`. Existe solo para
   * migrar campos de F4 con aspecto idéntico (casillas, radios y los campos que aún no pasan
   * al aspecto nuevo); se borra cuando el último pase a `Field`.
   */
  aspecto?: 'nuevo' | 'heredado';
};

/**
 * Campo de texto de una línea. Servible desde servidor. 16 px mínimo (`text-base`)
 * para que iOS no haga zoom al enfocarlo; la caja (alto, radio, borde, foco y error)
 * sale de `ui/caja-campo.ts`. Va dentro de `Field`, que le pone `id`,
 * `aria-describedby` y `aria-invalid`; solo, necesita su propia etiqueta.
 */
export function Input({ invalido, aspecto = 'nuevo', type = 'text', className, ...props }: InputProps) {
  const ariaInvalido = props['aria-invalid'];
  const malo = invalido ?? (ariaInvalido === true || ariaInvalido === 'true');

  return (
    <input
      {...props}
      type={type}
      aria-invalid={malo || undefined}
      className={
        aspecto === 'heredado' ? className : cn(
        malo ? CAJA_CAMPO_ERROR : CAJA_CAMPO,
        // El foco lo pinta la caja (borde `ring` de 2 px): sin contorno del navegador encima.
        'w-full py-3 outline-none disabled:cursor-not-allowed',
        className,
      )}
    />
  );
}
