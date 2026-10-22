'use client';

import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import { m, useReducedMotion } from 'framer-motion';
import {
  alTocar, bandaPrevia, celdasDelMes, estadoDeCelda, inicioDeMes, moverFoco, moverMes,
} from '@/lib/calendario-mes';
import type { ControlFecha } from '@/lib/control-fecha';
import { fromLocalISODate } from '@/lib/dates';
import { DURACION, transicion } from '@/lib/movimiento';
import { Button } from '../button';
import { cn } from '../cn';
import { Atajos } from './atajos';
import { CeldaDia } from './celda-dia';
import { Leyenda } from './leyenda';
import type { TextosCalendario } from './textos';

export type SeleccionFechas = { desde: string | null; hasta: string | null };

type Props = {
  locale: string;
  control: ControlFecha;
  seleccion: SeleccionFechas;
  onSeleccion: (seleccion: SeleccionFechas) => void;
  /** Primer día reservable (`getMinBookableDate`). */
  minDate: string;
  hoy: string;
  /** Noches del paquete (`rango_fijo_paquete`). */
  noches?: number | null;
  /** Días llenos para este grupo (`getCupoRango`); sin el dato, nada se marca. */
  sinCupo?: Record<string, unknown>;
  /** Este control tiene cupo que consultar (bajo demanda no): habilita «Sin cupo» en la leyenda. */
  conCupo?: boolean;
  cargando?: boolean;
  errorCupo?: boolean;
  onReintentar?: () => void;
  /** El mes que se ve, para que la ruta consulte su cupo. */
  onMesVisible?: (primerDia: string) => void;
  /** Dentro de la tarjeta de un paso (≥ 1024 px) no repite borde ni radio. */
  enTarjeta?: boolean;
  textos: TextosCalendario;
};

const NOCHES_ENTRE = (desde: string, hasta: string) =>
  Math.round((fromLocalISODate(hasta).getTime() - fromLocalISODate(desde).getTime()) / 86_400_000);

/** Iniciales de los días desde Intl (lunes primero): no se traducen a mano. */
const iniciales = (locale: string) => {
  const formato = new Intl.DateTimeFormat(locale, { weekday: 'short' });
  return Array.from({ length: 7 }, (_, i) => formato.format(new Date(2024, 0, 1 + i)).replace('.', '').slice(0, 2));
};

/**
 * El calendario completo de la reserva (sustituye la tira semanal). Siempre 6 semanas; la celda
 * entera es el área táctil (los días se exceptúan de la separación de 8 px). Fecha única: un toque
 * elige. Paquete con noches: un toque elige la llegada y la salida sale de las noches; si cruza el fin de
 * mes, el calendario pasa solo al mes de la salida. Llegada y salida o ida y regreso: con el dedo, el primer
 * toque fija el inicio y el segundo cierra; con ratón o teclado, pasar por encima o enfocar es la vista
 * previa y elegir confirma. Deslizar de lado
 * cambia de mes; teclado completo (flechas, Re Pág, Av Pág, Inicio, Fin, Esc).
 */
export function Calendario({
  locale, control, seleccion, onSeleccion, minDate, hoy, noches = null, sinCupo = {}, conCupo = true,
  cargando = false, errorCupo = false, onReintentar, onMesVisible, enTarjeta = false, textos,
}: Props) {
  const sinMovimiento = useReducedMotion();
  const [mes, setMes] = useState(() => inicioDeMes(seleccion.desde ?? (minDate > hoy ? minDate : hoy)));
  const [direccion, setDireccion] = useState<1 | -1>(1);
  const [previa, setPrevia] = useState<string | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);
  const [foco, setFoco] = useState<string | null>(null);
  const [avisoSinLugar, setAvisoSinLugar] = useState(false);
  const puntero = useRef<string>('mouse');
  const inicioToque = useRef<{ x: number; y: number } | null>(null);
  const enfocarDespues = useRef<string | null>(null);
  const cuadricula = useRef<HTMLDivElement>(null);

  useEffect(() => { onMesVisible?.(mes); }, [mes, onMesVisible]);
  useEffect(() => {
    const dia = enfocarDespues.current;
    if (!dia) return;
    enfocarDespues.current = null;
    cuadricula.current?.querySelector<HTMLElement>(`[data-dia="${dia}"]`)?.focus();
  });

  const cambiarMes = (delta: number) => {
    setDireccion(delta > 0 ? 1 : -1);
    setMes((actual) => moverMes(actual, delta));
  };
  const primerMes = inicioDeMes(minDate);

  // Llegada y salida o ida y regreso con solo el inicio elegido (el regreso no se prellena): el
  // siguiente toque cierra el rango desde ese inicio.
  const inicioPendiente = (control === 'rango_llegada_salida' || control === 'ida_y_regreso') && !seleccion.hasta
    ? seleccion.desde
    : null;
  const previaVigente = previa ?? inicioPendiente;
  // Rango fijo: la vista previa sigue al dedo o al foco; en los demás rangos, del inicio al día bajo él.
  const banda = control === 'rango_fijo_paquete'
    ? bandaPrevia(control, sobre ?? previa, null, noches)
    : bandaPrevia(control, previaVigente, sobre, noches);
  const ctx = { minDate, hoy, sinCupo, desde: seleccion.desde, hasta: seleccion.hasta, banda, conservarSeleccion: control === 'rango_fijo_paquete' };

  const formatoLargo = new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'long' });
  const formatoCorto = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' });

  const tocar = (iso: string) => {
    const estado = estadoDeCelda(iso, ctx);
    if (estado.base === 'no_reservable') return;
    if (estado.base === 'sin_cupo') {
      setAvisoSinLugar(true);
      return;
    }
    setAvisoSinLugar(false);
    const resultado = alTocar(control, previaVigente, iso, noches);
    setPrevia(resultado.previa);
    if (resultado.seleccion) {
      setSobre(null);
      onSeleccion(resultado.seleccion);
      // Un rango que termina en otro mes (una estancia que cruza el fin de mes) lleva el calendario a ese
      // mes: si no, la salida queda fuera de la vista y parece que no se eligió.
      const fin = resultado.seleccion.hasta;
      if (control === 'rango_fijo_paquete' && fin && inicioDeMes(fin) > mes) {
        setDireccion(1);
        setMes(inicioDeMes(fin));
      }
    }
  };

  const alTeclear = (evento: KeyboardEvent<HTMLDivElement>) => {
    if (evento.key === 'Escape') {
      setPrevia(null);
      setSobre(null);
      return;
    }
    const actual = foco ?? seleccion.desde ?? mes;
    const nuevo = moverFoco(actual, evento.key);
    if (!nuevo) return;
    evento.preventDefault();
    puntero.current = 'teclado';
    setFoco(nuevo);
    setSobre(nuevo);
    if (inicioDeMes(nuevo) !== mes) {
      setDireccion(nuevo > mes ? 1 : -1);
      setMes(inicioDeMes(nuevo));
    }
    enfocarDespues.current = nuevo;
  };

  const alBajar = (evento: PointerEvent) => {
    puntero.current = evento.pointerType;
    inicioToque.current = evento.pointerType === 'touch' ? { x: evento.clientX, y: evento.clientY } : null;
  };
  const alSubir = (evento: PointerEvent) => {
    const inicio = inicioToque.current;
    inicioToque.current = null;
    if (!inicio) return;
    const dx = evento.clientX - inicio.x;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(evento.clientY - inicio.y)) {
      if (dx > 0 && mes <= primerMes) return;
      cambiarMes(dx < 0 ? 1 : -1);
    }
  };

  const celdas = celdasDelMes(mes);
  const diasDelMes = celdas.filter((c): c is string => c !== null);
  // Una sola celda entra en el orden de tabulación (foco itinerante).
  const tabulado = [foco, seleccion.desde].find((d) => d && diasDelMes.includes(d))
    ?? diasDelMes.find((d) => d >= minDate) ?? diasDelMes[0];

  const anuncio = seleccion.desde && seleccion.hasta
    ? (control === 'ida_y_regreso' ? textos.anuncioIdaRegreso : textos.anuncioRango)
        .replace('{desde}', formatoCorto.format(fromLocalISODate(seleccion.desde)))
        .replace('{hasta}', formatoCorto.format(fromLocalISODate(seleccion.hasta)))
        .replace('{noches}', String(NOCHES_ENTRE(seleccion.desde, seleccion.hasta)))
    : seleccion.desde ? formatoLargo.format(fromLocalISODate(seleccion.desde)) : '';

  const etiquetaMes = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(fromLocalISODate(mes));
  // Rango abierto (llegada y salida, ida y regreso): una línea dice qué hace el siguiente toque.
  const abierto = control === 'rango_llegada_salida' || control === 'ida_y_regreso';
  // Con el rango ya completo no hace falta guía: el resumen de abajo dice las dos fechas.
  const completo = Boolean(seleccion.desde && seleccion.hasta) && !previa;
  const esperandoFin = Boolean(previaVigente);
  const guia = !abierto || completo ? null
    : control === 'ida_y_regreso'
      ? (esperandoFin ? textos.guiaRegreso : textos.guiaIda)
      : (esperandoFin ? textos.guiaSalida : textos.guiaLlegada);

  return (
    <div
      className={cn(
        'flex flex-col gap-4 rounded-card bg-blanco p-4 shadow-tarjeta',
        enTarjeta && 'lg:rounded-none lg:p-0 lg:shadow-none',
      )}
    >
      {guia && <p className="texto-pequeno text-apagado" aria-live="polite">{guia}</p>}
      <Atajos
        hoy={hoy}
        minDate={minDate}
        haySeleccion={seleccion.desde !== null}
        onBorrar={() => {
          setPrevia(null);
          onSeleccion({ desde: null, hasta: null });
        }}
        onElegir={(iso) => {
          setMes(inicioDeMes(iso));
          puntero.current = 'mouse';
          tocar(iso);
        }}
        textos={textos}
      />
      <div className="flex items-center justify-between gap-2">
        <Button
          variante="libre"
          type="button"
          onClick={() => cambiarMes(-1)}
          disabled={mes <= primerMes}
          aria-label={textos.mesAnterior}
          className="flex size-12 shrink-0 items-center justify-center rounded-full text-cafe transition-colors hover:bg-cafe-bruma disabled:cursor-not-allowed disabled:text-borde-control disabled:hover:bg-transparent"
        >
          <CaretLeft size={20} weight="bold" aria-hidden />
        </Button>
        {/* El mes es un titular de la marca: Consola Mono en mayúsculas, como el título del paso. */}
        <p className="texto-mono-mayus text-xl font-bold text-foreground" aria-live="polite">{etiquetaMes}</p>
        <Button
          variante="libre"
          type="button"
          onClick={() => cambiarMes(1)}
          aria-label={textos.mesSiguiente}
          className="flex size-12 shrink-0 items-center justify-center rounded-full text-cafe transition-colors hover:bg-cafe-bruma"
        >
          <CaretRight size={20} weight="bold" aria-hidden />
        </Button>
      </div>

      <div
        ref={cuadricula}
        role="grid"
        aria-label={etiquetaMes}
        onKeyDown={alTeclear}
        onPointerDown={alBajar}
        onPointerUp={alSubir}
        onPointerLeave={() => setSobre(null)}
        className="touch-pan-y select-none"
      >
        <div role="row" className="grid grid-cols-[repeat(7,minmax(0,1fr))] pb-1">
          {iniciales(locale).map((inicial, i) => (
            <span key={i} role="columnheader" className="text-center texto-mono-mayus texto-pie text-apagado">
              {inicial}
            </span>
          ))}
        </div>
        <m.div
          key={mes}
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, x: direccion * 24 }}
          animate={sinMovimiento ? { opacity: 1 } : { opacity: 1, x: 0 }}
          transition={transicion(sinMovimiento, DURACION.larga)}
        >
          {Array.from({ length: 6 }, (_, fila) => (
            <div key={fila} role="row" className="grid grid-cols-[repeat(7,minmax(0,1fr))]">
              {celdas.slice(fila * 7, fila * 7 + 7).map((iso, i) => {
                if (!iso) return <span key={`vacio-${fila}-${i}`} role="gridcell" className="h-11" />;
                const estado = estadoDeCelda(iso, ctx);
                const elegido = estado.marca === 'seleccion' || estado.marca === 'extremo';
                const motivo = estado.base === 'no_reservable' ? textos.noReservable
                  : estado.base === 'sin_cupo' ? textos.sinLugar : '';
                return (
                  <span key={iso} role="gridcell" aria-selected={elegido}>
                    <Button
                      variante="libre"
                      type="button"
                      data-dia={iso}
                      tabIndex={iso === tabulado ? 0 : -1}
                      // Sin cupo sigue enfocable: al tocarlo dice por qué no se puede.
                      aria-disabled={estado.base !== 'disponible' || undefined}
                      aria-label={[formatoLargo.format(fromLocalISODate(iso)), motivo].filter(Boolean).join('. ')}
                      onClick={() => tocar(iso)}
                      onPointerEnter={(e) => { if (e.pointerType !== 'touch') setSobre(iso); }}
                      onFocus={() => { setFoco(iso); setSobre(iso); }}
                      className={cn(
                        'group block w-full rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                        estado.base === 'no_reservable' && 'cursor-not-allowed',
                      )}
                    >
                      <CeldaDia numero={Number(iso.slice(8))} estado={estado} />
                    </Button>
                  </span>
                );
              })}
            </div>
          ))}
        </m.div>
      </div>

      <p role="status" className={cn('texto-pequeno text-foreground', !avisoSinLugar && 'sr-only')}>
        {avisoSinLugar ? textos.sinLugar : ''}
      </p>
      <p className="sr-only" aria-live="polite">{anuncio}</p>

      {conCupo && cargando && !errorCupo && <p className="texto-pequeno text-apagado">{textos.consultando}</p>}
      {conCupo && errorCupo && (
        <div role="status" className="flex flex-col items-start gap-2 rounded-control bg-info-fondo p-3 texto-pequeno text-info">
          <p>{textos.errorCupo}</p>
          {onReintentar && (
            <Button variante="libre" type="button" onClick={onReintentar} className="min-h-11 font-semibold underline">
              {textos.reintentar}
            </Button>
          )}
        </div>
      )}

      <Leyenda control={control} conCupo={conCupo} marcaHoy={hoy >= mes && hoy < moverMes(mes, 1)} textos={textos.leyenda} />
    </div>
  );
}
