'use client';

import { useId, useState, type ReactNode } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { CalendarDots, CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { Despliegue } from '@/components/checkout/despliegue';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
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

/**
 * Cambia de semana deslizando en la dirección del click: adelante entra por la
 * derecha, atrás por la izquierda. Una dirección coherente le dice al ojo qué
 * viene; redibujar los 7 días de golpe no le da nada que predecir.
 */
function Deslizable({ clave, direccion, children, className }: {
  clave: string; direccion: 1 | -1; children: ReactNode; className?: string;
}) {
  const sinMovimiento = useReducedMotion();
  const desplazamiento = sinMovimiento ? 0 : 20;
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={clave} className={className}
        initial={{ opacity: 0, x: direccion * desplazamiento }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -direccion * desplazamiento }}
        transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export function FechaPaquete({
  lang, value, onChange, minDate, label, chooseLabel, viewMonthLabel, hideMonthLabel,
  previousWeekLabel, nextWeekLabel, previousMonthLabel, nextMonthLabel, personas, fullLabel, sinEncabezado = false,
}: Props) {
  const locale = intlLocale(lang);
  const [inicioVisible, setInicioVisible] = useState(() => semanaVisible(value, minDate).inicio);
  const [valorAnterior, setValorAnterior] = useState(value);
  const [minimoAnterior, setMinimoAnterior] = useState(minDate);
  const [mesAbierto, setMesAbierto] = useState(false);
  const [inicioPrevio, setInicioPrevio] = useState(inicioVisible);
  const [direccion, setDireccion] = useState<1 | -1>(1);
  const panelId = useId();
  const seleccionVigente = value && value >= minDate ? value : null;

  // La fecha de regreso puede dejar de valer al cambiar el inicio del paquete.
  if (value !== valorAnterior || minDate !== minimoAnterior) {
    setValorAnterior(value);
    setMinimoAnterior(minDate);
    setInicioVisible(semanaVisible(value, minDate).inicio);
  }

  // Hacia dónde se movió la semana (sea por las flechas o porque se eligió una
  // fecha lejana): de ahí sale el lado por el que entran los días nuevos.
  if (inicioVisible !== inicioPrevio) {
    setDireccion(inicioVisible > inicioPrevio ? 1 : -1);
    setInicioPrevio(inicioVisible);
  }

  const { dias } = semanaVisible(inicioVisible, minDate);
  const formatoCompleto = new Intl.DateTimeFormat(locale, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
  const formatoDia = new Intl.DateTimeFormat(locale, { weekday: 'short' });
  // Los 7 días arrancan donde arranca la disponibilidad, no en lunes: casi
  // siempre cruzan de mes, y entonces el rótulo dice el rango real.
  const primerDia = fromLocalISODate(dias[0]);
  const ultimoDia = fromLocalISODate(dias[6]);
  const formatoCorto = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' });
  const etiquetaMes = primerDia.getMonth() === ultimoDia.getMonth()
    ? new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(primerDia)
    : `${formatoCorto.format(primerDia).replace('.', '')} – ${formatoCorto.format(ultimoDia).replace('.', '')}`;

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
        <Deslizable clave={etiquetaMes} direccion={direccion}>
          <span className="block text-sm font-medium text-foreground first-letter:uppercase">{etiquetaMes}</span>
        </Deslizable>
        <button type="button" onClick={() => moverSemana(1)} aria-label={nextWeekLabel}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground">
          <CaretRight size={17} />
        </button>
      </div>

      <Deslizable clave={inicioVisible} direccion={direccion} className="mt-2 grid grid-cols-7 gap-1 sm:gap-2">
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
      </Deslizable>

      <div className="mt-1">
        <AccionTexto tono="acento" abierto={mesAbierto} aria-controls={mesAbierto ? panelId : undefined}
          icono={<CalendarDots size={14} />}
          onClick={() => setMesAbierto((abierto) => !abierto)}>
          {mesAbierto ? hideMonthLabel : viewMonthLabel}
        </AccionTexto>
      </div>

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
  /** "Modificar" / "Listo": el botón de la fila, que solo existe cuando ya hay respuesta. */
  changeButtonLabel: string;
  doneButtonLabel: string;
};

/**
 * La fecha de regreso es obligatoria, así que mientras no haya respuesta se ve
 * la pregunta con la tira semanal abierta: un botón "Elegir" la haría parecer
 * opcional y sumaría un paso. Al contestar se pliega a una fila ("Regreso: sáb
 * 12 oct") y recién entonces aparece "Modificar", como las tarjetas del
 * checkout. No se prellena: sin respuesta se muestra la pregunta, no una fecha
 * que el cliente no eligió.
 */
export function FechaRegresoCompacta({ changeButtonLabel, doneButtonLabel, ...props }: PropsCompacta) {
  const { lang, value, minDate, label, chooseLabel, onChange } = props;
  const [abierta, setAbierta] = useState(false);
  const locale = intlLocale(lang);
  const vigente = value && value >= minDate ? value : null;
  const formato = new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div>
      <Despliegue abierto={!vigente}>
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="mt-1 text-sm text-muted">{chooseLabel}</p>
      </Despliegue>
      <Despliegue abierto={Boolean(vigente)}>
        <button type="button" aria-expanded={abierta} onClick={() => setAbierta((a) => !a)}
          className="group flex w-full items-center justify-between gap-3 text-left">
          <span className="min-w-0">
            <span className="block text-sm font-medium text-foreground">{label}</span>
            <span className="mt-0.5 block truncate text-sm text-foreground first-letter:uppercase">
              {vigente ? formato.format(fromLocalISODate(vigente)).replace('.', '') : ''}
            </span>
          </span>
          <span className="shrink-0 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition-colors group-hover:border-accent group-hover:text-accent">
            {abierta ? doneButtonLabel : changeButtonLabel}
          </span>
        </button>
      </Despliegue>
      <Despliegue abierto={!vigente || abierta}>
        <div className="mt-4">
          <FechaPaquete {...props} sinEncabezado onChange={(fecha) => { onChange(fecha); setAbierta(false); }} />
        </div>
      </Despliegue>
    </div>
  );
}
