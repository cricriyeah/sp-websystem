'use client';

import { useState } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import { Deslizable } from '@/components/checkout/deslizable';
import type { Locale } from '@/app/[lang]/dictionaries';
import { puedeRetroceder, semanaVisible } from '@/lib/calendario-semana';
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

export function CheckoutCalendar({
  lang,
  selected,
  onSelect,
  minDate,
  weekdaysShort,
  personas,
  fullLabel,
}: CheckoutCalendarProps) {
  // La tira arranca en el primer día reservable y avanza de 7 en 7 (ver
  // `lib/calendario-semana`): sin celdas pasadas que no se pueden tocar.
  const [inicio, setInicio] = useState(() => semanaVisible(selected, minDate).inicio);

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
    const deLaSeleccion = semanaVisible(selected, minDate).inicio;
    if (deLaSeleccion !== inicio) setInicio(deLaSeleccion);
  }

  // Hacia dónde se movió la semana (flechas, o porque se aceptó un día lejano):
  // de ahí sale el lado por el que entran los días nuevos.
  const [inicioPrevio, setInicioPrevio] = useState(inicio);
  const [direccion, setDireccion] = useState<1 | -1>(1);
  if (inicio !== inicioPrevio) {
    setDireccion(inicio > inicioPrevio ? 1 : -1);
    setInicioPrevio(inicio);
  }

  const days = semanaVisible(inicio, minDate).dias.map((iso) => fromLocalISODate(iso));

  const { dias: disponibilidad, cargando } = useDisponibilidad(
    toIso(days[0]),
    toIso(days[6]),
    personas,
  );

  // Los 7 días casi nunca caen en un solo mes: entonces el rótulo dice el rango.
  const formatoMes = new Intl.DateTimeFormat(intlLocale(lang), { month: 'long', year: 'numeric' });
  const formatoCorto = new Intl.DateTimeFormat(intlLocale(lang), { day: 'numeric', month: 'short' });
  const etiquetaMes = days[0].getMonth() === days[6].getMonth()
    ? formatoMes.format(days[0])
    : `${formatoCorto.format(days[0]).replace('.', '')} – ${formatoCorto.format(days[6]).replace('.', '')}`;
  const capitalizedMonth = etiquetaMes.charAt(0).toUpperCase() + etiquetaMes.slice(1);

  const shiftWeek = (delta: number) => {
    const next = fromLocalISODate(inicio);
    next.setDate(next.getDate() + delta * 7);
    setInicio(toIso(next));
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => shiftWeek(-1)}
          disabled={!puedeRetroceder(inicio, minDate)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
        >
          <CaretLeft size={16} />
        </button>
        <Deslizable clave={capitalizedMonth} direccion={direccion}>
          <p className="text-sm font-medium text-foreground">{capitalizedMonth}</p>
        </Deslizable>
        <button
          type="button"
          onClick={() => shiftWeek(1)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground"
        >
          <CaretRight size={16} />
        </button>
      </div>

      <Deslizable clave={inicio} direccion={direccion} className="mt-4 grid grid-cols-7 gap-2">
        {days.map((date) => {
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
                cargando && !isPast ? 'opacity-50 motion-safe:animate-pulse ' : ''
              }${
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
              <span className="text-[11px] opacity-80">{weekdaysShort[(date.getDay() + 6) % 7]}</span>
              <span className="font-medium">{date.getDate()}</span>
            </button>
          );
        })}
      </Deslizable>

      {/* No va en un `title`: Chrome no muestra el tooltip de un boton
          deshabilitado y en movil no hay hover. */}
      {Object.values(disponibilidad).some(Boolean) && (
        <p className="mt-3 text-[11px] leading-snug text-muted">{fullLabel}</p>
      )}
    </div>
  );
}
