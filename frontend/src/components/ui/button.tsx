import type { ComponentProps, MouseEvent } from 'react';
// El barril normal de Phosphor usa contexto de cliente; `/ssr` deja a Button servible desde servidor.
import { ArrowRight } from '@phosphor-icons/react/ssr';
import { cn } from './cn';
import { botonClases, type TamanoBoton, type VarianteBoton } from './variantes';

type ButtonProps = ComponentProps<'button'> & {
  variante?: VarianteBoton;
  tamano?: TamanoBoton;
  /** Flecha a la derecha de la etiqueta (destino de un paso). */
  conFlecha?: boolean;
  /**
   * Acción en curso. Usa `aria-busy` y `aria-disabled` y NO `disabled`: un botón
   * deshabilitado pierde el foco y el lector de pantalla deja de anunciarlo justo
   * cuando el cliente espera la respuesta. Mientras tanto `onClick` se ignora.
   */
  cargando?: boolean;
};

/**
 * Única forma de pintar un botón fuera de `ui/`. Sin `'use client'` ni `motion`:
 * se puede usar desde un Server Component. En React 19 `ref` es una prop normal.
 *
 * `type="button"` por defecto: un `<button>` sin tipo dentro de un `<form>` envía
 * el formulario. Quien quiera enviar lo pide con `type="submit"`.
 *
 * `className` se fusiona al final con `cn`, así que puede sustituir cualquier
 * clase de la variante (p. ej. `px-4` gana a `px-6`).
 */
export function Button({
  variante,
  tamano,
  conFlecha = false,
  cargando = false,
  type = 'button',
  className,
  onClick,
  children,
  ...props
}: ButtonProps) {
  const alPulsar = (evento: MouseEvent<HTMLButtonElement>) => {
    if (cargando) {
      // Sin `disabled` el navegador no frena solo el envío de un `type="submit"`.
      evento.preventDefault();
      return;
    }
    onClick?.(evento);
  };

  return (
    <button
      {...props}
      type={type}
      onClick={alPulsar}
      aria-busy={cargando || undefined}
      aria-disabled={cargando ? true : props['aria-disabled']}
      className={cn(botonClases({ variante, tamano }), cargando && 'cursor-progress opacity-60', className)}
    >
      {children}
      {conFlecha && <ArrowRight size={16} weight="bold" aria-hidden="true" />}
    </button>
  );
}
