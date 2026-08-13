'use client';

import { useState } from 'react';
import { CalendarBlank, CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { FieldPopover } from '@/components/field-popover';
import { fromLocalISODate, toLocalISODate } from '@/lib/dates';
import { intlLocale } from '@/lib/intl';

type DateFieldProps = {
  lang: Locale;
  label: string;
  value: string;
  onChange: (isoDate: string) => void;
  minDate: string;
  prevMonthLabel: string;
  nextMonthLabel: string;
};

const inicioDeMes = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1);

/** Lunes = 0, para que la semana empiece en lunes como en Mexico. */
const diaDeSemanaLunes = (date: Date) => (date.getDay() + 6) % 7;

/** Iniciales de los dias, sacadas de Intl: no hay que traducirlas a mano. */
function inicialesDeDias(locale: string) {
  const formato = new Intl.DateTimeFormat(locale, { weekday: 'short' });
  // 2024-01-01 fue lunes; sirve de ancla para recorrer una semana completa.
  return Array.from({ length: 7 }, (_, i) => {
    const dia = new Date(2024, 0, 1 + i);
    return formato.format(dia).replace('.', '').slice(0, 2);
  });
}

export function DateField({
  lang,
  label,
  value,
  onChange,
  minDate,
  prevMonthLabel,
  nextMonthLabel,
}: DateFieldProps) {
  const locale = intlLocale(lang);
  const [mesVisible, setMesVisible] = useState(() => inicioDeMes(fromLocalISODate(value)));

  const seleccionada = fromLocalISODate(value);
  const diasDelMes = new Date(mesVisible.getFullYear(), mesVisible.getMonth() + 1, 0).getDate();
  const huecosIniciales = diaDeSemanaLunes(mesVisible);

  const etiquetaMes = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(mesVisible);
  const etiquetaValor = new Intl.DateTimeFormat(locale, {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  }).format(seleccionada);

  const moverMes = (delta: number) =>
    setMesVisible((actual) => new Date(actual.getFullYear(), actual.getMonth() + delta, 1));

  return (
    <FieldPopover
      label={label}
      value={etiquetaValor}
      icon={<CalendarBlank size={20} className="shrink-0 text-muted" />}
      // Encabezado + iniciales + 6 filas de dias, con el mes mas largo posible.
      alturaEstimada={360}
    >
      {(cerrar) => (
        <div className="w-72">
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => moverMes(-1)}
              aria-label={prevMonthLabel}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground"
            >
              <CaretLeft size={16} />
            </button>
            <p className="text-sm font-medium text-foreground first-letter:uppercase">{etiquetaMes}</p>
            <button
              type="button"
              onClick={() => moverMes(1)}
              aria-label={nextMonthLabel}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground"
            >
              <CaretRight size={16} />
            </button>
          </div>

          <div className="mt-3 grid grid-cols-7 gap-1 text-center text-[11px] text-muted">
            {inicialesDeDias(locale).map((inicial, i) => (
              <span key={i} className="py-1 first-letter:uppercase">
                {inicial}
              </span>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: huecosIniciales }, (_, i) => <span key={`hueco-${i}`} />)}

            {Array.from({ length: diasDelMes }, (_, i) => {
              const dia = new Date(mesVisible.getFullYear(), mesVisible.getMonth(), i + 1);
              const iso = toLocalISODate(dia);
              const esSeleccionada = iso === value;
              const deshabilitada = iso < minDate;

              return (
                <button
                  key={iso}
                  type="button"
                  disabled={deshabilitada}
                  aria-pressed={esSeleccionada}
                  onClick={() => {
                    onChange(iso);
                    cerrar();
                  }}
                  className={`flex h-9 items-center justify-center rounded-lg text-sm transition-colors ${
                    esSeleccionada
                      ? 'bg-accent font-medium text-accent-foreground'
                      : deshabilitada
                        ? 'cursor-not-allowed text-muted/35'
                        : 'text-foreground hover:bg-background'
                  }`}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </FieldPopover>
  );
}
