'use client';

import { useEffect, useRef, useState } from 'react';
import { Minus, Plus, UsersThree } from '@phosphor-icons/react';
import { MAX_PEOPLE, MIN_PEOPLE } from '@/lib/dates';

type PeopleStepperProps = {
  label: string;
  /** Aviso que aparece al intentar pasar del maximo. */
  maxNotice: string;
  /** `null` = todavia no contesta. Se muestra la pregunta en vez de una cifra. */
  value: number | null;
  onChange: (value: number) => void;
  disabled?: boolean;
  /** Pregunta grande mientras no hay respuesta. */
  placeholder?: string;
  /** Cuantas personas se asumen al pulsar + desde vacio. */
  valorInicial?: number;
};

/**
 * Contador de personas, compartido por el booking bar y el checkout. El tope
 * son 6 (la embarcacion mas grande) y el backend lo valida igual, ver
 * `MAX_PERSONAS` en apps/bookings/models.py.
 */
export function PeopleStepper({
  label,
  maxNotice,
  value,
  onChange,
  disabled,
  placeholder,
  valorInicial = 2,
}: PeopleStepperProps) {
  const vacio = value === null;
  const [showMaxNotice, setShowMaxNotice] = useState(false);
  const noticeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
  }, []);

  const ajustar = (delta: number) => {
    // Desde vacio, cualquiera de los dos botones contesta la pregunta con el
    // grupo mas comun en vez de obligar a subir de uno en uno desde cero.
    if (value === null) {
      onChange(valorInicial);
      return;
    }
    const siguiente = value + delta;
    if (siguiente > MAX_PEOPLE) {
      setShowMaxNotice(true);
      if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
      noticeTimeout.current = setTimeout(() => setShowMaxNotice(false), 2500);
      onChange(MAX_PEOPLE);
      return;
    }
    onChange(Math.min(MAX_PEOPLE, Math.max(MIN_PEOPLE, siguiente)));
  };

  return (
    <div className="relative flex flex-1 items-center gap-3 rounded-2xl px-6 py-4">
      <UsersThree size={20} className="shrink-0 text-muted" />
      <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
        {!vacio && <span className="text-xs text-muted">{label}</span>}
        <span className="flex w-full items-center justify-between">
          <span
            className={`whitespace-nowrap ${
              vacio ? 'text-sm font-medium text-foreground/70' : 'text-sm text-foreground'
            }`}
          >
            {vacio ? placeholder : value}
          </span>
          <span className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => ajustar(-1)}
              disabled={disabled || (value !== null && value <= MIN_PEOPLE)}
              aria-label="-"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
            >
              <Minus size={12} />
            </button>
            <button
              type="button"
              onClick={() => ajustar(1)}
              disabled={disabled}
              aria-label="+"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
            >
              <Plus size={12} />
            </button>
          </span>
        </span>
      </span>

      {showMaxNotice && (
        <span className="absolute -bottom-8 left-0 z-10 rounded-lg bg-foreground px-3 py-1.5 text-xs whitespace-nowrap text-surface shadow-lg">
          {maxNotice}
        </span>
      )}
    </div>
  );
}
