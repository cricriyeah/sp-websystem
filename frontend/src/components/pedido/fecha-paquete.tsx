'use client';

import { useId, useState } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { Despliegue } from '@/components/checkout/despliegue';
import { PanelCalendario } from '@/components/date-field';
import { puedeRetroceder, semanaVisible } from '@/lib/calendario-semana';
import { fromLocalISODate, toLocalISODate } from '@/lib/dates';
import { intlLocale } from '@/lib/intl';

type Props = {
  lang: Locale;
  value: string | null;
  onChange: (fecha: string) => void;
  minDate: string;
  label: string;
  chooseLabel: string;
  viewMonthLabel: string;
  hideMonthLabel: string;
  previousWeekLabel: string;
  nextWeekLabel: string;
  previousMonthLabel: string;
  nextMonthLabel: string;
  personas: number;
  fullLabel: string;
  /** Sin la etiqueta ni la fecha elegida arriba: las pinta quien lo envuelve (fila compacta). */
  sinEncabezado?: boolean;
};

export function FechaPaquete({
  lang, value, onChange, minDate, label, chooseLabel, viewMonthLabel, hideMonthLabel,
  previousWeekLabel, nextWeekLabel, previousMonthLabel, nextMonthLabel, personas, fullLabel, sinEncabezado = false,
}: Props) {
  const locale = intlLocale(lang);
  const [inicioVisible, setInicioVisible] = useState(() => semanaVisible(value, minDate).inicio);
  const [valorAnterior, setValorAnterior] = useState(value);
  const [minimoAnterior, setMinimoAnterior] = useState(minDate);
  const [mesAbierto, setMesAbierto] = useState(false);
  const panelId = useId();
  const seleccionVigente = value && value >= minDate ? value : null;

  // La fecha de regreso puede dejar de valer al cambiar el inicio del paquete.
  if (value !== valorAnterior || minDate !== minimoAnterior) {
    setValorAnterior(value);
    setMinimoAnterior(minDate);
    setInicioVisible(semanaVisible(value, minDate).inicio);
  }

  const { dias } = semanaVisible(inicioVisible, minDate);
  const formatoCompleto = new Intl.DateTimeFormat(locale, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
  const formatoDia = new Intl.DateTimeFormat(locale, { weekday: 'short' });
  const etiquetaMes = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' })
    .format(fromLocalISODate(dias[3]));

  const moverSemana = (semanas: number) => {
    const lunes = fromLocalISODate(inicioVisible);
    lunes.setDate(lunes.getDate() + semanas * 7);
    setInicioVisible(toLocalISODate(lunes));
  };

  const elegir = (fecha: string) => {
    onChange(fecha);
    setMesAbierto(false);
  };

  return (
    <div>
      {!sinEncabezado && (
        <>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className={`mt-1 text-sm first-letter:uppercase ${seleccionVigente ? 'text-foreground' : 'text-muted'}`}>
            {seleccionVigente ? formatoCompleto.format(fromLocalISODate(seleccionVigente)) : chooseLabel}
          </p>
        </>
      )}

      <div className={`${sinEncabezado ? '' : 'mt-4 '}flex items-center justify-between gap-3`}>
        <button type="button" onClick={() => moverSemana(-1)}
          disabled={!puedeRetroceder(inicioVisible, minDate)} aria-label={previousWeekLabel}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30">
          <CaretLeft size={17} />
        </button>
        <span className="text-sm font-medium text-foreground first-letter:uppercase">{etiquetaMes}</span>
        <button type="button" onClick={() => moverSemana(1)} aria-label={nextWeekLabel}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground">
          <CaretRight size={17} />
        </button>
      </div>

      <div className="mt-2 grid grid-cols-7 gap-1 sm:gap-2">
        {dias.map((iso) => {
          const fecha = fromLocalISODate(iso);
          const seleccionada = iso === seleccionVigente;
          const pasada = iso < minDate;
          return (
            <button key={iso} type="button" disabled={pasada} aria-label={formatoCompleto.format(fecha)}
              aria-pressed={seleccionada} onClick={() => elegir(iso)}
              className={`flex min-h-14 min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg border px-0.5 py-2 text-sm transition-colors ${
                seleccionada ? 'border-accent bg-accent font-medium text-accent-foreground'
                  : pasada ? 'cursor-not-allowed border-border text-muted/40'
                    : 'border-border text-foreground hover:border-accent hover:bg-surface'
              }`}>
              <span className="text-[11px] first-letter:uppercase">{formatoDia.format(fecha).replace('.', '').slice(0, 2)}</span>
              <span>{fecha.getDate()}</span>
            </button>
          );
        })}
      </div>

      <button type="button" aria-expanded={mesAbierto} aria-controls={mesAbierto ? panelId : undefined}
        onClick={() => setMesAbierto((abierto) => !abierto)}
        className="mt-3 text-sm font-medium text-accent underline underline-offset-4 hover:text-foreground">
        {mesAbierto ? hideMonthLabel : viewMonthLabel}
      </button>

      <Despliegue abierto={mesAbierto}>
        <div id={panelId} className="mt-3 rounded-lg border border-border bg-surface p-4">
          <PanelCalendario
            locale={locale} value={seleccionVigente ?? minDate} seleccionado={seleccionVigente}
            onChange={elegir} minDate={minDate} personas={personas} fullLabel={fullLabel}
            prevMonthLabel={previousMonthLabel} nextMonthLabel={nextMonthLabel}
            sinCupo={true} cerrar={() => setMesAbierto(false)} anchoCompleto
          />
        </div>
      </Despliegue>
    </div>
  );
}

type PropsCompacta = Omit<Props, 'sinEncabezado'> & {
  /** "Elegir" / "Modificar" / "Listo": el botón de la fila. */
  chooseButtonLabel: string;
  changeButtonLabel: string;
  doneButtonLabel: string;
};

/**
 * La fecha de regreso del traslado es secundaria frente al inicio del paquete:
 * una fila ("Regreso: sáb 12 oct") y la tira semanal solo si el cliente la pide.
 * No se prellena: sin respuesta se muestra la pregunta, no una fecha inventada.
 */
export function FechaRegresoCompacta({ chooseButtonLabel, changeButtonLabel, doneButtonLabel, ...props }: PropsCompacta) {
  const { lang, value, minDate, label, chooseLabel, onChange } = props;
  const [abierta, setAbierta] = useState(false);
  const locale = intlLocale(lang);
  const vigente = value && value >= minDate ? value : null;
  const formato = new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className={`mt-0.5 truncate text-sm first-letter:uppercase ${vigente ? 'text-foreground' : 'text-muted'}`}>
            {vigente ? formato.format(fromLocalISODate(vigente)).replace('.', '') : chooseLabel}
          </p>
        </div>
        <button type="button" aria-expanded={abierta} onClick={() => setAbierta((a) => !a)}
          className="shrink-0 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-accent hover:text-accent">
          {abierta ? doneButtonLabel : vigente ? changeButtonLabel : chooseButtonLabel}
        </button>
      </div>
      <Despliegue abierto={abierta}>
        <div className="mt-4">
          <FechaPaquete {...props} sinEncabezado onChange={(fecha) => { onChange(fecha); setAbierta(false); }} />
        </div>
      </Despliegue>
    </div>
  );
}
