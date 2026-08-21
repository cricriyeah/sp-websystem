'use client';

import { useState } from 'react';
import { CalendarBlank, CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { FieldPopover } from '@/components/field-popover';
import { fromLocalISODate, toLocalISODate } from '@/lib/dates';
import { useDisponibilidad } from '@/lib/disponibilidad';
import { intlLocale } from '@/lib/intl';

type DateFieldProps = {
  lang: Locale;
  label: string;
  /** `null` = todavia no contesta: se muestra la pregunta en vez de una fecha. */
  value: string | null;
  onChange: (isoDate: string) => void;
  minDate: string;
  prevMonthLabel: string;
  nextMonthLabel: string;
  /** Cuantas personas van. Un dia puede tener lugar para 2 y no para 4. */
  personas: number;
  /** Leyenda del dia sin lugar. */
  fullLabel: string;
  /** Pregunta grande mientras no hay respuesta. */
  placeholder?: string;
  solicitarApertura?: number;
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
  personas,
  fullLabel,
  placeholder,
  solicitarApertura,
}: DateFieldProps) {
  const locale = intlLocale(lang);

  const etiquetaValor = value
    ? new Intl.DateTimeFormat(locale, {
        weekday: 'short',
        day: '2-digit',
        month: 'short',
      }).format(fromLocalISODate(value))
    : '';

  return (
    <FieldPopover
      label={label}
      value={etiquetaValor}
      vacio={value === null}
      placeholder={placeholder}
      solicitarApertura={solicitarApertura}
      icon={<CalendarBlank size={20} className="shrink-0 text-muted" />}
      // Encabezado + iniciales + 6 filas de dias, con el mes mas largo posible.
      alturaEstimada={360}
    >
      {(cerrar) => (
        <PanelCalendario
          locale={locale}
          value={value ?? minDate}
          seleccionado={value}
          onChange={onChange}
          minDate={minDate}
          personas={personas}
          fullLabel={fullLabel}
          prevMonthLabel={prevMonthLabel}
          nextMonthLabel={nextMonthLabel}
          cerrar={cerrar}
        />
      )}
    </FieldPopover>
  );
}


/**
 * El mes en si. Vive aparte porque `FieldPopover` solo renderiza sus hijos
 * cuando esta abierto: asi la consulta de disponibilidad se dispara al abrir el
 * calendario y no en cada visita a la portada, que es estatica y no deberia
 * pegarle a la API para nada.
 */
function PanelCalendario({
  locale,
  value,
  seleccionado,
  onChange,
  minDate,
  personas,
  fullLabel,
  prevMonthLabel,
  nextMonthLabel,
  cerrar,
}: {
  locale: string;
  /** Mes que se abre. Sin respuesta todavia, es el primer dia disponible. */
  value: string;
  /** La fecha elegida, o null si aun no hay ninguna: sin ella no se pinta nada
   *  como seleccionado, para no sugerir una eleccion que el cliente no hizo. */
  seleccionado: string | null;
  onChange: (isoDate: string) => void;
  minDate: string;
  personas: number;
  fullLabel: string;
  prevMonthLabel: string;
  nextMonthLabel: string;
  cerrar: () => void;
}) {
  const [mesVisible, setMesVisible] = useState(() => inicioDeMes(fromLocalISODate(value)));

  const diasDelMes = new Date(mesVisible.getFullYear(), mesVisible.getMonth() + 1, 0).getDate();
  const huecosIniciales = diaDeSemanaLunes(mesVisible);

  const primerDia = toLocalISODate(mesVisible);
  const ultimoDia = toLocalISODate(
    new Date(mesVisible.getFullYear(), mesVisible.getMonth(), diasDelMes),
  );
  const { dias: disponibilidad, cargando } = useDisponibilidad(primerDia, ultimoDia, personas);

  const etiquetaMes = new Intl.DateTimeFormat(locale, {
    month: 'long',
    year: 'numeric',
  }).format(mesVisible);

  const hayDiasLlenos = Object.values(disponibilidad).some(Boolean);

  const moverMes = (delta: number) =>
    setMesVisible((actual) => new Date(actual.getFullYear(), actual.getMonth() + delta, 1));

  return (
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
        {Array.from({ length: huecosIniciales }, (_, i) => (
          <span key={`hueco-${i}`} />
        ))}

        {Array.from({ length: diasDelMes }, (_, i) => {
          const dia = new Date(mesVisible.getFullYear(), mesVisible.getMonth(), i + 1);
          const iso = toLocalISODate(dia);
          const esSeleccionada = iso === seleccionado;
          const pasada = iso < minDate;
          // Sin lugar para ESTE grupo. Mientras la consulta no responde el mapa
          // esta vacio y no se agrisa nada: nunca se bloquea un dia por no saber.
          const sinLugar = Boolean(disponibilidad[iso]);
          const deshabilitada = pasada || sinLugar;

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
                // Mientras no sabemos, los dias futuros se atenuan en vez de
                // verse plenamente disponibles: asi el tachado que llega medio
                // segundo despues no es un cambio de contenido a la vista.
                cargando && !pasada ? 'opacity-50 motion-safe:animate-pulse ' : ''
              }${
                // Lleno gana sobre seleccionado: pintar de naranja un dia que no
                // se puede tomar dice "elegido y todo bien" y contradice al resto
                // de la pantalla. Conserva el anillo, pierde el relleno.
                sinLugar
                  ? `cursor-not-allowed text-muted/50 line-through decoration-muted/40 ${
                      esSeleccionada ? 'ring-1 ring-accent' : ''
                    }`
                  : esSeleccionada
                    ? 'bg-accent font-medium text-accent-foreground'
                    : pasada
                      ? 'cursor-not-allowed text-muted/35'
                      : 'text-foreground hover:bg-background'
              }`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      {/* La explicacion va aqui y no en un `title`: Chrome no muestra el tooltip
          de un boton deshabilitado, y en movil no hay hover. Solo aparece si de
          verdad hay algun dia tachado en el mes que se esta viendo. */}
      {hayDiasLlenos && (
        <p className="mt-3 border-t border-border pt-2 text-[11px] leading-snug text-muted">
          {fullLabel}
        </p>
      )}
    </div>
  );
}
