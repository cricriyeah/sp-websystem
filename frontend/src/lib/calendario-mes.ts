// La lógica del calendario de reserva, sin React: la cuadrícula del mes, el estado de cada día,
// qué hace un toque según el control de fecha, los atajos y el teclado. `ui/calendario` la pinta.
import { sumarDias } from './calendario-paquete';
import type { ControlFecha } from './control-fecha';
import { fromLocalISODate, toLocalISODate } from './dates';

/** Lunes = 0: la semana empieza en lunes, como en México. */
const diaSemana = (iso: string) => (fromLocalISODate(iso).getDay() + 6) % 7;

export function inicioDeMes(iso: string): string {
  const fecha = fromLocalISODate(iso);
  return toLocalISODate(new Date(fecha.getFullYear(), fecha.getMonth(), 1));
}

export function moverMes(primerDia: string, delta: number): string {
  const fecha = fromLocalISODate(primerDia);
  return toLocalISODate(new Date(fecha.getFullYear(), fecha.getMonth() + delta, 1));
}

/** Siempre 42 celdas (6 semanas): el calendario no cambia de alto al cambiar de mes. */
export function celdasDelMes(primerDia: string): (string | null)[] {
  const inicio = fromLocalISODate(primerDia);
  const total = new Date(inicio.getFullYear(), inicio.getMonth() + 1, 0).getDate();
  const huecos = diaSemana(primerDia);
  return Array.from({ length: 42 }, (_, i) => {
    const dia = i - huecos + 1;
    return dia >= 1 && dia <= total ? toLocalISODate(new Date(inicio.getFullYear(), inicio.getMonth(), dia)) : null;
  });
}

export type BaseCelda = 'disponible' | 'no_reservable' | 'sin_cupo';
export type MarcaCelda = 'ninguna' | 'seleccion' | 'extremo' | 'rango' | 'vista_previa';

export type ContextoCelda = {
  minDate: string;
  hoy: string;
  /** Lo que `getCupoRango` declara lleno (cualquier motivo no nulo). */
  sinCupo: Record<string, unknown>;
  desde: string | null;
  hasta: string | null;
  /** Días de la vista previa, en orden. */
  banda: readonly string[];
};

export type EstadoCelda = {
  base: BaseCelda;
  marca: MarcaCelda;
  hoy: boolean;
  /** Extremos de la banda (de la vista previa o del rango firme): ahí nace o muere en el centro. */
  inicioBanda: boolean;
  finBanda: boolean;
};

export function estadoDeCelda(iso: string, ctx: ContextoCelda): EstadoCelda {
  const base: BaseCelda = iso < ctx.minDate ? 'no_reservable' : ctx.sinCupo[iso] ? 'sin_cupo' : 'disponible';
  const hoy = iso === ctx.hoy;
  // Mientras se elige de nuevo, la vista previa manda sobre lo ya elegido.
  if (ctx.banda.length > 0) {
    const dentro = ctx.banda.includes(iso);
    return {
      base, hoy,
      marca: dentro ? 'vista_previa' : 'ninguna',
      inicioBanda: dentro && ctx.banda[0] === iso,
      finBanda: dentro && ctx.banda[ctx.banda.length - 1] === iso,
    };
  }
  if (ctx.desde && ctx.hasta && iso >= ctx.desde && iso <= ctx.hasta) {
    const extremo = iso === ctx.desde || iso === ctx.hasta;
    return { base, hoy, marca: extremo ? 'extremo' : 'rango', inicioBanda: iso === ctx.desde, finBanda: iso === ctx.hasta };
  }
  return { base, hoy, marca: ctx.desde === iso ? 'seleccion' : 'ninguna', inicioBanda: false, finBanda: false };
}

export type ResultadoToque = { seleccion?: { desde: string; hasta: string | null }; previa: string | null };

/**
 * Un toque en `iso`. Fecha única: elige. Paquete con noches: un toque elige la llegada y la salida sale de
 * las noches (no hay nada que confirmar: antes pedía un segundo toque y se sentía roto). Llegada y salida
 * o ida y regreso: el primer toque fija el inicio y uno posterior cierra el rango; uno igual o anterior
 * reemplaza el inicio.
 */
export function alTocar(control: ControlFecha, previa: string | null, iso: string, noches: number | null): ResultadoToque {
  if (control === 'fecha_unica') return { seleccion: { desde: iso, hasta: null }, previa: null };
  if (control === 'rango_fijo_paquete') {
    return { seleccion: { desde: iso, hasta: sumarDias(iso, Math.max(0, noches ?? 0)) }, previa: null };
  }
  return previa && iso > previa ? { seleccion: { desde: previa, hasta: iso }, previa: null } : { previa: iso };
}

/** Los días de la vista previa: el rango fijo desde `previa`, o del inicio al día bajo el dedo o el foco. */
export function bandaPrevia(control: ControlFecha, previa: string | null, sobre: string | null, noches: number | null): string[] {
  if (!previa || control === 'fecha_unica') return [];
  const largo = control === 'rango_fijo_paquete'
    ? Math.max(0, noches ?? 0)
    : sobre && sobre > previa ? Math.round((fromLocalISODate(sobre).getTime() - fromLocalISODate(previa).getTime()) / 86_400_000) : 0;
  return Array.from({ length: largo + 1 }, (_, i) => sumarDias(previa, i));
}

export type Atajo = { clave: 'manana' | 'en2'; fecha: string; antesDelMinimo: boolean };

/** «Mañana» y «En 2 días», relativos a hoy; antes del mínimo de anticipación se deshabilitan. */
export function atajos(hoy: string, minDate: string): Atajo[] {
  return ([['manana', 1], ['en2', 2]] as const).map(([clave, dias]) => {
    const fecha = sumarDias(hoy, dias);
    return { clave, fecha, antesDelMinimo: fecha < minDate };
  });
}

/** El día al que va el foco con una tecla; `null` si la tecla no mueve el foco. */
export function moverFoco(iso: string, tecla: string): string | null {
  switch (tecla) {
    case 'ArrowRight': return sumarDias(iso, 1);
    case 'ArrowLeft': return sumarDias(iso, -1);
    case 'ArrowDown': return sumarDias(iso, 7);
    case 'ArrowUp': return sumarDias(iso, -7);
    case 'Home': return sumarDias(iso, -diaSemana(iso));
    case 'End': return sumarDias(iso, 6 - diaSemana(iso));
    case 'PageDown':
    case 'PageUp': {
      const fecha = fromLocalISODate(iso);
      const delta = tecla === 'PageDown' ? 1 : -1;
      const ultimo = new Date(fecha.getFullYear(), fecha.getMonth() + delta + 1, 0).getDate();
      return toLocalISODate(new Date(fecha.getFullYear(), fecha.getMonth() + delta, Math.min(fecha.getDate(), ultimo)));
    }
    default: return null;
  }
}
