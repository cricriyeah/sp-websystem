'use client';

import { useEffect, useRef, useState } from 'react';
import { Minus, Plus, UsersThree } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
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
  /** Tope configurable de personas. Vacio = MAX_PEOPLE (5). */
  maxPeople?: number;
  minPeople?: number;
};

/**
 * Contador de personas, compartido por el booking bar y el checkout.
 * El tope por omisión es MAX_PEOPLE (5) de pesca o el que indique el servicio.
 */
export function PeopleStepper({
  label,
  maxNotice,
  value,
  onChange,
  disabled,
  placeholder,
  valorInicial = 2,
  maxPeople,
  minPeople,
}: PeopleStepperProps) {
  const vacio = value === null;
  const [showMaxNotice, setShowMaxNotice] = useState(false);
  const noticeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sinMovimiento = useReducedMotion();
  const max = maxPeople ?? MAX_PEOPLE;
  const min = minPeople ?? MIN_PEOPLE;

  useEffect(() => () => {
    if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
  }, []);

  const ajustar = (delta: number) => {
    // Desde vacio, cualquiera de los dos botones contesta la pregunta con el
    // grupo mas comun en vez de obligar a subir de uno en uno desde cero.
    if (value === null) {
      onChange(Math.min(max, Math.max(min, valorInicial)));
      return;
    }
    const siguiente = value + delta;
    if (siguiente > max) {
      setShowMaxNotice(true);
      if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
      noticeTimeout.current = setTimeout(() => setShowMaxNotice(false), 2500);
      onChange(max);
      return;
    }
    onChange(Math.min(max, Math.max(min, siguiente)));
  };

  return (
    <div className="relative flex flex-1 items-center gap-3 px-6 py-3.5">
      <UsersThree size={20} className="shrink-0 text-muted" />
      {/* Alto reservado, igual que en FieldPopover: la etiqueta solo existe una
          vez contestado, y dejar que el contenido mande el alto hacia que la
          barra entera creciera al contestar. Ver el comentario largo alla. */}
      <span className="flex h-10 flex-1 flex-col items-start justify-center gap-0.5 text-left">
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

      <AnimatePresence>
        {showMaxNotice && (
          <motion.span
            key="max-notice"
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4 }}
            transition={{ duration: 0.16 }}
            className="absolute -bottom-8 left-0 z-10 rounded-lg bg-foreground px-3 py-1.5 text-xs whitespace-nowrap text-surface shadow-lg"
          >
            {maxNotice}
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}
