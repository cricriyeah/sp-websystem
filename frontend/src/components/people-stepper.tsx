'use client';

import { useEffect, useRef, useState } from 'react';
import { Minus, Plus, UsersThree } from '@phosphor-icons/react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { MAX_PEOPLE, MIN_PEOPLE } from '@/lib/dates';
import { Button } from '@/components/ui/button';
import { useCambioPrecio } from '@/components/checkout/cambio-precio';

type PeopleStepperProps = {
  label: string;
  /** Aviso que aparece al intentar pasar del maximo. */
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
  /** Tope configurable de personas. Vacio = MAX_PEOPLE (5). */
  maxPeople?: number;
  minPeople?: number;
  /** Dentro de una tarjeta del checkout: relleno de 16 px y botones con contraste normal. */
  compacto?: boolean;
};

// Compacto: 40 px dentro de una caja de 56, para que los botones no queden pegados al borde. Sin compactar
// (la barra de reserva), 36 px: la etiqueta y los botones tienen que caber juntos en el alto reservado.
const botonStepper = (compacto: boolean) =>
  compacto
    ? 'flex size-10 shrink-0 items-center justify-center rounded-full border border-borde-control text-foreground transition-[color,border-color,scale] duration-150 hover:border-accent hover:text-accent active:scale-90 motion-reduce:active:scale-100 disabled:opacity-30'
    : 'flex size-9 shrink-0 items-center justify-center rounded-full text-muted transition-[background-color,scale] duration-150 hover:bg-border active:scale-90 motion-reduce:active:scale-100 disabled:opacity-30';

/**
 * Contador de personas, compartido por el booking bar y el checkout.
 * El tope por omisión es MAX_PEOPLE (5) de pesca o el que indique el servicio.
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
  const [showMaxNotice, setShowMaxNotice] = useState(false);
  const noticeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sinMovimiento = useReducedMotion();
  const max = maxPeople ?? MAX_PEOPLE;
  const min = minPeople ?? MIN_PEOPLE;
  // Cuánto cambió el precio con este toque, junto al contador (si la ruta lo mide: `ProveedorCambioPrecio`).
  const cambio = useCambioPrecio('-top-3 right-2');
  // Hacia dónde entra el número nuevo: desde abajo al sumar, desde arriba al restar.
  const [sentido, setSentido] = useState<1 | -1>(1);

  useEffect(() => () => {
    if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
  }, []);

  const ajustar = (delta: number) => {
    cambio.marcar();
    setSentido(delta > 0 ? 1 : -1);
    // Desde vacio, cualquiera de los dos botones contesta la pregunta con el
    // grupo mas comun en vez de obligar a subir de uno en uno desde cero.
    if (value === null) {
      onChange(Math.min(max, Math.max(min, valorInicial)));
      return;
    }
    const siguiente = value + delta;
    if (siguiente > max) {
      onMaxAttempt?.();
      setShowMaxNotice(true);
      if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
      noticeTimeout.current = setTimeout(() => setShowMaxNotice(false), 2500);
      onChange(max);
      return;
    }
    onChange(Math.min(max, Math.max(min, siguiente)));
  };

  return (
    <div className={`relative flex flex-1 items-center gap-3 ${compacto ? 'px-4 py-2' : 'px-6 py-3.5'}`}>
      <UsersThree size={compacto ? 24 : 20} className="shrink-0 text-muted" />
      {/* Compacto: la pregunta va encima de la caja (la pone quien lo usa, con `CampoEtiquetado`) y adentro
          queda una sola línea de 40 px. Sin compactar, la etiqueta se suma encima del valor al contestar: el
          alto va reservado (46 px) para que la barra no crezca de golpe, y los botones se centran a la derecha
          en vez de empujar el contenido hacia el borde de abajo. */}
      <span className={`flex flex-1 items-center justify-between gap-3 text-left ${compacto ? 'min-h-10' : 'min-h-[2.875rem]'}`}>
        <span className="flex min-w-0 flex-col justify-center gap-0.5">
          {!vacio && !compacto && <span className="text-sm text-muted">{label}</span>}
          <span
            className={`relative inline-grid overflow-hidden whitespace-nowrap ${
              vacio ? 'text-base font-medium text-foreground/70 sm:text-sm' : 'text-base text-foreground sm:text-sm'
            }`}
          >
            <AnimatePresence initial={false} mode="popLayout" custom={sentido}>
              <m.span
                key={vacio ? 'vacio' : value}
                custom={sentido}
                initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: `${sentido * 70}%` }}
                animate={{ opacity: 1, y: 0 }}
                exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: `${sentido * -70}%` }}
                transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
                className="col-start-1 row-start-1 tabular-nums"
              >
                {vacio ? placeholder : value}
              </m.span>
            </AnimatePresence>
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <Button
            variante="libre"
            type="button"
            onClick={() => ajustar(-1)}
            disabled={disabled || (value !== null && value <= MIN_PEOPLE)}
            aria-label="-"
            className={botonStepper(compacto)}
          >
            <Minus size={16} />
          </Button>
          <Button
            variante="libre"
            type="button"
            onClick={() => ajustar(1)}
            disabled={disabled}
            aria-label="+"
            className={botonStepper(compacto)}
          >
            <Plus size={16} />
          </Button>
        </span>
      </span>

      {cambio.pildora}
      <AnimatePresence>
        {showMaxNotice && (
          <m.span
            key="max-notice"
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4 }}
            transition={{ duration: 0.16 }}
            className={`absolute left-0 z-10 rounded-sm bg-foreground px-3 py-1.5 text-sm whitespace-nowrap text-cafe-bruma shadow-n2 ${
              // En un cuadro con scroll (compacto) el borde de abajo lo recorta pegado al pie con
              // "Confirmar": el aviso sube. En la barra de reserva sigue abajo, donde sí cabe.
              compacto ? 'bottom-full mb-1.5' : '-bottom-8'
            }`}
          >
            {maxNotice}
          </m.span>
        )}
      </AnimatePresence>
    </div>
  );
}
