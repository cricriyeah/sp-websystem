'use client';

import { cloneElement, useId, useLayoutEffect, useRef, useState, type ReactElement } from 'react';
import { WarningCircle } from '@phosphor-icons/react';
import { cn } from './cn';
import { useLlevarAlError } from './error-de-campo';

type PropsDelControl = {
  id?: string;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean | 'true' | 'false';
};

type FieldProps = {
  etiqueta: string;
  /** Mensaje de error; vacío o ausente = sin error. El renglón de error siempre está montado. */
  error?: string | null;
  ayuda?: string;
  /** Un solo control (`Input`, un selector…) al que Field le inyecta `id` y las props de accesibilidad. */
  children: ReactElement<PropsDelControl>;
  className?: string;
};

/**
 * Etiqueta arriba, control, y debajo un solo renglón para la ayuda o el error.
 *
 * - Etiqueta de 14 px en peso 600 y `tinta`, a 8 px del control; ayuda de 14 px en `apagado`.
 * - El renglón de abajo mide como mínimo 20 px y está SIEMPRE montado, con o sin texto: lo que
 *   hay debajo no brinca cuando aparece un error. Si hay error y ayuda, el error reemplaza a la
 *   ayuda en el mismo renglón. No se anima la altura, solo un fundido de opacidad de 150 ms.
 * - Con un error de dos renglones (máximo dos en 360 px, o se acorta el texto) la altura se mide
 *   una vez y se conserva, así que un segundo error no vuelve a mover la página.
 * - El error lleva icono (`WarningCircle` de 16) y texto: nunca solo color.
 *
 * Isla cliente porque genera el `id` con `useId()` para enlazar la etiqueta (`htmlFor`) y, con
 * `aria-describedby`, la ayuda y el error: sin ese enlace el mensaje existe a la vista pero no
 * para quien usa lector de pantalla. Si el error aparece fuera de pantalla, trae el campo a la
 * vista y le da el foco (`useLlevarAlError`).
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

  // Conserva el último texto mientras el error se funde (el estado ya lo vació).
  const [ultimo, setUltimo] = useState('');
  if (error && error !== ultimo) setUltimo(error);

  // Altura del renglón: se mide cuando hay error y se reserva (solo crece).
  const renglon = useRef<HTMLDivElement>(null);
  const [alto, setAlto] = useState(0);
  useLayoutEffect(() => {
    if (!hayError || !renglon.current) return;
    const medido = renglon.current.offsetHeight;
    setAlto((anterior) => (medido > anterior ? medido : anterior));
  }, [hayError, ultimo]);

  useLlevarAlError(idError, hayError);

  // Solo se enlaza lo que se ve: el error cuando hay uno, la ayuda cuando no lo hay.
  const describedby =
    [children.props['aria-describedby'], ayuda && !hayError ? idAyuda : null, hayError ? idError : null]
      .filter(Boolean)
      .join(' ') || undefined;

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <label htmlFor={id} className="texto-pequeno font-semibold text-tinta">
        {etiqueta}
      </label>
      {cloneElement(children, {
        id,
        'aria-describedby': describedby,
        'aria-invalid': hayError ? true : children.props['aria-invalid'],
      })}
      <div ref={renglon} className="grid min-h-5" style={alto ? { minHeight: alto } : undefined}>
        {ayuda && (
          <p
            id={idAyuda}
            aria-hidden={hayError || undefined}
            className={cn(
              'texto-pequeno col-start-1 row-start-1 text-apagado transition-opacity duration-[var(--duracion-corta)]',
              hayError && 'opacity-0',
            )}
          >
            {ayuda}
          </p>
        )}
        <p
          id={idError}
          role="alert"
          className={cn(
            'texto-pequeno col-start-1 row-start-1 flex items-start gap-1.5 text-error transition-opacity duration-[var(--duracion-corta)]',
            !hayError && 'opacity-0',
          )}
        >
          {ultimo && (
            <>
              <WarningCircle size={16} weight="fill" aria-hidden="true" className="mt-0.5 shrink-0" />
              <span>{ultimo}</span>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
