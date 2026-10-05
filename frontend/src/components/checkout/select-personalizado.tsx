'use client';

import type { ReactNode } from 'react';
import { ListBullets } from '@phosphor-icons/react';
import { FieldPopover } from '@/components/field-popover';

type Opcion = { valor: string; etiqueta: string };

type Props = {
  /** La pregunta: etiqueta chica al contestar, texto grande mientras está vacío. */
  label: string;
  value: string;
  opciones: Opcion[];
  onChange: (valor: string) => void;
  /** Texto grande mientras no hay respuesta; por defecto, la pregunta misma. */
  placeholder?: string;
  icon?: ReactNode;
  /** Opción para volver a "sin respuesta" (los datos que no son obligatorios). */
  sinRespuestaLabel?: string;
  disabled?: boolean;
  invalido?: boolean;
};

/**
 * Elegir de una lista corta con el mismo campo que ya usa el resto del
 * checkout (`FieldPopover`), en vez del `<select>` nativo cuyo desplegable lo
 * pinta el sistema operativo: dos widgets para la misma decisión se leen como
 * dos tareas distintas.
 *
 * No va dentro de un `<label>`: el clic sobre una etiqueta activaría el botón
 * del campo y lo abriría sin querer.
 */
export function SelectPersonalizado({
  label, value, opciones, onChange, placeholder, icon, sinRespuestaLabel, disabled = false, invalido = false,
}: Props) {
  const actual = opciones.find((o) => o.valor === value);
  return (
    <div
      aria-disabled={disabled || undefined}
      className={`border bg-surface ${invalido ? 'border-red-400' : 'border-border'} ${disabled ? 'pointer-events-none opacity-60' : ''}`}
    >
      <FieldPopover
        label={label}
        value={actual?.etiqueta ?? ''}
        vacio={!actual}
        placeholder={placeholder ?? label}
        icon={icon ?? <ListBullets size={20} className="shrink-0 text-muted" />}
      >
        {(cerrar) => (
          <div className="max-h-72 w-full overflow-y-auto sm:w-80">
            {sinRespuestaLabel && (
              <button type="button" onClick={() => { onChange(''); cerrar(); }}
                className="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-muted transition-colors hover:bg-background">
                {sinRespuestaLabel}
              </button>
            )}
            {opciones.map((opcion) => (
              <button key={opcion.valor} type="button"
                onClick={() => { onChange(opcion.valor); cerrar(); }}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  opcion.valor === value ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground hover:bg-background'
                }`}>
                <span className="truncate pr-2">{opcion.etiqueta}</span>
              </button>
            ))}
          </div>
        )}
      </FieldPopover>
    </div>
  );
}
