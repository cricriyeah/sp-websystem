'use client';

import { cloneElement, useId, type ReactElement } from 'react';
import { cn } from './cn';
import { ErrorDeCampo } from './error-de-campo';

type PropsDelControl = {
  id?: string;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean | 'true' | 'false';
};

type FieldProps = {
  etiqueta: string;
  /** Mensaje de error; vacío o ausente = sin error. El bloque de error siempre está montado. */
  error?: string | null;
  ayuda?: string;
  /** Un solo control (`Input`, un selector…) al que Field le inyecta `id` y las props de accesibilidad. */
  children: ReactElement<PropsDelControl>;
  className?: string;
};

/**
 * Etiqueta arriba, control, ayuda y error debajo. Isla cliente porque genera el
 * `id` con `useId()` para enlazar la etiqueta (`htmlFor`) y, con
 * `aria-describedby`, la ayuda y el error: sin ese enlace el mensaje existe a la
 * vista pero no para quien usa lector de pantalla.
 *
 * Recibe el control como elemento (no como función) para poder usarse desde un
 * Server Component: una función no cruza la frontera servidor-cliente.
 */
export function Field({ etiqueta, error, ayuda, children, className }: FieldProps) {
  const generado = useId();
  const id = children.props.id ?? generado;
  const idAyuda = `${id}-ayuda`;
  const idError = `${id}-error`;
  const hayError = Boolean(error);

  // Solo se enlaza el error cuando hay uno: el nodo sigue montado mientras se pliega.
  const describedby =
    [children.props['aria-describedby'], ayuda ? idAyuda : null, hayError ? idError : null]
      .filter(Boolean)
      .join(' ') || undefined;

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <label htmlFor={id} className="texto-etiqueta text-foreground">
        {etiqueta}
      </label>
      {cloneElement(children, {
        id,
        'aria-describedby': describedby,
        'aria-invalid': hayError ? true : children.props['aria-invalid'],
      })}
      {ayuda && (
        <p id={idAyuda} className="texto-pequeno text-apagado">
          {ayuda}
        </p>
      )}
      <ErrorDeCampo id={idError} mensaje={error} />
    </div>
  );
}
