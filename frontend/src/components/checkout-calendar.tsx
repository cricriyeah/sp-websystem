'use client';

import { useState } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { fromLocalISODate, toLocalISODate } from '@/lib/dates';
import { useDisponibilidad } from '@/lib/disponibilidad';
import { intlLocale } from '@/lib/intl';

type CheckoutCalendarProps = {
  lang: Locale;
  selected: string;
  onSelect: (isoDate: string) => void;
  minDate: string;
  weekdaysShort: string[];
  /** Cuantas personas van: el mismo dia admite a 2 y rechaza a 4. */
  personas: number;
  /** Leyenda del dia sin lugar, para el title del boton deshabilitado. */
  fullLabel: string;
};

const toIso = toLocalISODate;

function startOfWeek(date: Date) {
  const start = new Date(date);
  const day = (start.getDay() + 6) % 7; // 0 = Monday
  start.setDate(start.getDate() - day);
  return start;
}

export function CheckoutCalendar({
  lang,
  selected,
  onSelect,
  minDate,
  weekdaysShort,
  personas,
  fullLabel,
}: CheckoutCalendarProps) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(fromLocalISODate(selected)));

  // Si la fecha elegida cae fuera de la semana que se esta viendo, la tira la
  // sigue. Hace falta desde que aceptar el dia que ofrecemos es un clic del
  // cliente: la alternativa suele caer en la semana siguiente, y sin esto el
  // calendario se quedaba en la semana vieja, sin mostrar por ningun lado la
  // fecha que el acababa de aceptar.
  //
  // Va como ajuste durante el render y no en un efecto: es el patron que React
  // documenta para reaccionar a un cambio de prop, se resuelve antes de pintar
  // (sin el parpadeo de la semana vieja) y no dispara `set-state-in-effect`.
  const [seleccionPrevia, setSeleccionPrevia] = useState(selected);
  if (selected !== seleccionPrevia) {
    setSeleccionPrevia(selected);
    const semanaDeLaSeleccion = startOfWeek(fromLocalISODate(selected));
    if (semanaDeLaSeleccion.getTime() !== weekStart.getTime()) {
      setWeekStart(semanaDeLaSeleccion);
    }
  }

  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(weekStart);
    date.setDate(date.getDate() + i);
    return date;
  });

  const disponibilidad = useDisponibilidad(toIso(days[0]), toIso(days[6]), personas);

  const monthLabel = new Intl.DateTimeFormat(intlLocale(lang), {
    month: 'long',
    year: 'numeric',
  }).format(days[0]);
  const capitalizedMonth = monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);

  const shiftWeek = (delta: number) => {
    const next = new Date(weekStart);
    next.setDate(next.getDate() + delta * 7);
    setWeekStart(next);
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => shiftWeek(-1)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground"
        >
          <CaretLeft size={16} />
        </button>
        <p className="text-sm font-medium text-foreground">{capitalizedMonth}</p>
        <button
          type="button"
          onClick={() => shiftWeek(1)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground"
        >
          <CaretRight size={16} />
        </button>
      </div>

      <div className="mt-4 grid grid-cols-7 gap-2">
        {days.map((date, i) => {
          const iso = toIso(date);
          const isSelected = iso === selected;
          const isPast = iso < minDate;
          // Sin lugar para ESTE grupo. Mientras la consulta no responde el mapa
          // esta vacio y no se agrisa nada: no se bloquea un dia por no saber.
          const isFull = Boolean(disponibilidad[iso]);
          const isDisabled = isPast || isFull;

          return (
            <button
              key={iso}
              type="button"
              disabled={isDisabled}
              onClick={() => onSelect(iso)}
              className={`flex flex-col items-center gap-1 rounded-xl border px-1 py-2.5 text-xs transition-colors ${
                // Un dia lleno nunca se pinta como seleccion normal, aunque sea
                // el elegido: llegar por URL con una fecha que ya se lleno
                // dejaba el dia en naranja —"elegido y todo bien"— contradiciendo
                // el aviso de arriba. Conserva el borde de seleccion, pierde el
                // relleno, y se tacha como cualquier otro dia sin lugar.
                isFull
                  ? `cursor-not-allowed text-muted/50 line-through decoration-muted/40 ${
                      isSelected ? 'border-accent' : 'border-border'
                    }`
                  : isSelected
                    ? 'border-accent bg-accent text-accent-foreground'
                    : isPast
                      ? 'cursor-not-allowed border-border text-muted/40'
                      : 'border-border text-foreground hover:border-accent/50'
              }`}
            >
              <span className="text-[11px] opacity-80">{weekdaysShort[i]}</span>
              <span className="font-medium">{date.getDate()}</span>
            </button>
          );
        })}
      </div>

      {/* No va en un `title`: Chrome no muestra el tooltip de un boton
          deshabilitado y en movil no hay hover. */}
      {Object.values(disponibilidad).some(Boolean) && (
        <p className="mt-3 text-[11px] leading-snug text-muted">{fullLabel}</p>
      )}
    </div>
  );
}
