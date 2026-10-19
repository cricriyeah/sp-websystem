'use client';

import { useState } from 'react';
import { Minus, Plus, UsersThree } from '@phosphor-icons/react';
import { MAX_PEOPLE, MIN_PEOPLE } from '@/lib/dates';
import { Button } from '@/components/ui/button';
import { Despliegue } from '@/components/ui/despliegue';

type PeopleStepperProps = {
  label: string;
  /** «Máximo N personas»: se explica en línea al tocar + en el tope, en vez de ignorar el toque. */
  maxNotice: string;
  onMaxAttempt?: () => void;
  /** `null` = todavia no contesta. Se muestra la pregunta en vez de una cifra. */
  value: number | null;
  onChange: (value: number) => void;
  disabled?: boolean;
  /** Pregunta grande mientras no hay respuesta. */
  placeholder?: string;
  /** Cuantas personas se asumen al pulsar + desde vacio. */
  valorInicial?: number;
  /** Tope del servicio (`capacidad_maxima`). Vacio = MAX_PEOPLE (5). */
  maxPeople?: number;
  minPeople?: number;
  /** Dentro de una caja del checkout (`CAJA_CONTENEDOR`): relleno de 16 px. */
  compacto?: boolean;
};

/**
 * Contador de personas del checkout (design-components.md, «Contador de personas»): dos botones
 * secundarios circulares de 48 con el valor en 20/600 entre ellos. El tope por omisión es
 * MAX_PEOPLE (5) de pesca o el que indique el servicio.
 */
export function PeopleStepper({
  label,
  maxNotice,
  onMaxAttempt,
  value,
  onChange,
  disabled,
  placeholder,
  valorInicial = 2,
  maxPeople,
  minPeople,
  compacto = false,
}: PeopleStepperProps) {
  const vacio = value === null;
  const [enTope, setEnTope] = useState(false);
  const max = maxPeople ?? MAX_PEOPLE;
  const min = minPeople ?? MIN_PEOPLE;

  const ajustar = (delta: number) => {
    // Desde vacio, cualquiera de los dos botones contesta la pregunta con el
    // grupo mas comun en vez de obligar a subir de uno en uno desde cero.
    if (value === null) {
      onChange(Math.min(max, Math.max(min, valorInicial)));
      return;
    }
    const siguiente = value + delta;
    if (siguiente > max) {
      onMaxAttempt?.();
      setEnTope(true);
      onChange(max);
      return;
    }
    setEnTope(false);
    onChange(Math.min(max, Math.max(min, siguiente)));
  };

  return (
    // Dentro de su caja de campo: relleno de 16 a los lados para que los círculos no toquen el borde.
    <div className={compacto ? 'px-4 py-3' : 'px-4 py-2'}>
      <div className="flex items-center gap-3">
        <UsersThree size={20} className="shrink-0 text-muted" aria-hidden />
        <span className="min-w-0 flex-1 text-sm leading-snug font-medium text-foreground">{vacio ? placeholder : label}</span>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variante="secundario"
            tamano="icono"
            type="button"
            onClick={() => ajustar(-1)}
            disabled={disabled || (value !== null && value <= min)}
            aria-label={`${label}: -1`}
          >
            <Minus size={20} weight="bold" aria-hidden />
          </Button>
          <span className="min-w-8 text-center text-xl font-semibold tabular-nums text-foreground" aria-live="polite">
            {vacio ? '–' : value}
          </span>
          <Button
            variante="secundario"
            tamano="icono"
            type="button"
            onClick={() => ajustar(1)}
            disabled={disabled}
            aria-label={`${label}: +1`}
          >
            <Plus size={20} weight="bold" aria-hidden />
          </Button>
        </div>
      </div>
      <Despliegue abierto={enTope && value === max}>
        <p role="status" className="pt-2 text-right texto-pequeno text-apagado">{maxNotice}</p>
      </Despliegue>
    </div>
  );
}
