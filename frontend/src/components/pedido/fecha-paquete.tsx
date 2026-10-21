'use client';

import { useState } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CalendarioReserva } from '@/components/checkout/calendario-reserva';
import { Button } from '@/components/ui/button';
import { Despliegue } from '@/components/ui/despliegue';
import { fromLocalISODate } from '@/lib/dates';
import { intlLocale } from '@/lib/intl';

type Props = {
  lang: Locale;
  textos: Dictionary['checkout']['calendario'];
  value: string | null;
  onChange: (fecha: string | null) => void;
  minDate: string;
  label: string;
  chooseLabel: string;
  /** "Modificar" / "Listo": el botón de la fila, que solo existe cuando ya hay respuesta. */
  changeButtonLabel: string;
  doneButtonLabel: string;
  personas: number;
};

/**
 * La fecha de regreso del traslado dentro de un paquete. Es obligatoria, así que mientras no haya
 * respuesta se ve la pregunta con el calendario abierto: un botón "Elegir" la haría parecer
 * opcional y sumaría un paso. Al contestar se pliega a una fila ("Regreso: sáb 12 oct") y recién
 * entonces aparece "Modificar", como las tarjetas del checkout. No se prellena: sin respuesta se
 * muestra la pregunta, no una fecha que el cliente no eligió.
 */
export function FechaRegresoCompacta({
  lang, textos, value, onChange, minDate, label, chooseLabel, changeButtonLabel, doneButtonLabel, personas,
}: Props) {
  const [abierta, setAbierta] = useState(false);
  const vigente = value && value >= minDate ? value : null;
  const formato = new Intl.DateTimeFormat(intlLocale(lang), { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div>
      <Despliegue abierto={!vigente}>
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="mt-1 text-sm text-muted">{chooseLabel}</p>
      </Despliegue>
      <Despliegue abierto={Boolean(vigente)}>
        <Button variante="libre" type="button" aria-expanded={abierta} onClick={() => setAbierta((a) => !a)}
          className="group flex w-full items-center justify-between gap-3 text-left">
          <span className="min-w-0">
            <span className="block text-sm font-medium text-foreground">{label}</span>
            <span className="mt-0.5 block truncate text-sm text-foreground first-letter:capitalize">
              {vigente ? formato.format(fromLocalISODate(vigente)).replace('.', '') : ''}
            </span>
          </span>
          <span className="inline-flex min-h-11 shrink-0 items-center rounded-full border border-borde-control bg-cafe-bruma px-4 text-base font-medium text-foreground transition-colors group-hover:border-accent group-hover:text-accent sm:text-sm">
            {abierta ? doneButtonLabel : changeButtonLabel}
          </span>
        </Button>
      </Despliegue>
      <Despliegue abierto={!vigente || abierta}>
        <div className="mt-4">
          <CalendarioReserva
            lang={lang}
            textos={textos}
            control="fecha_unica"
            seleccion={{ desde: vigente, hasta: null }}
            onSeleccion={({ desde }) => {
              onChange(desde);
              if (desde) setAbierta(false);
            }}
            minDate={minDate}
            personas={personas}
            conCupo={false}
          />
        </div>
      </Despliegue>
    </div>
  );
}
