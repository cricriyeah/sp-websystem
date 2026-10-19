// Pantallas del asistente móvil (< 640 px): una sola se ve a la vez, «Continuar»
// lleva a la siguiente y la flecha a la anterior. Es una capa aparte de las
// tarjetas de escritorio; solo comparte los tres pasos de `pasos-checkout` para
// la línea de progreso. Sin React: cada ruta dice sus condiciones y aquí se
// decide la lista y el orden.
import type { PasoId } from './pasos-checkout';

export type TipoPantalla =
  | 'viaje'
  | 'extras'
  | 'inicio'
  | 'servicio'
  | 'tipo'
  | 'fecha'
  | 'hora-pasajeros'
  | 'contacto'
  | 'recogida'
  | 'como-pagas'
  | 'tarjeta';

export type Pantalla = {
  /** Único en la ruta; es lo que viaja en la URL. */
  id: string;
  tipo: TipoPantalla;
  paso: PasoId;
  /** Servicio del paquete (`servicio`) o empresa que cobra (`tarjeta`); 0 en las demás. */
  indice: number;
};

export type RutaAsistente =
  | { tipo: 'servicio'; tieneExtras: boolean }
  /** `empresas` > 1 es cruza-empresa: una pantalla de tarjeta por cada cobro. */
  | { tipo: 'paquete'; servicios: number; conTraslado: boolean; empresas: number }
  | { tipo: 'traslado' };

const PASO_DE: Record<TipoPantalla, PasoId> = {
  viaje: 'viaje',
  extras: 'viaje',
  inicio: 'viaje',
  servicio: 'viaje',
  tipo: 'viaje',
  fecha: 'viaje',
  'hora-pasajeros': 'viaje',
  contacto: 'datos',
  recogida: 'datos',
  'como-pagas': 'pago',
  tarjeta: 'pago',
};

function pantalla(tipo: TipoPantalla, indice = 0): Pantalla {
  const repetible = tipo === 'servicio' || tipo === 'tarjeta';
  return { id: repetible ? `${tipo}-${indice}` : tipo, tipo, paso: PASO_DE[tipo], indice };
}

function repetir(tipo: TipoPantalla, veces: number): Pantalla[] {
  return Array.from({ length: Math.max(1, veces) }, (_, i) => pantalla(tipo, i));
}

export function pantallasDe(ruta: RutaAsistente): Pantalla[] {
  const pago = (empresas: number) => [pantalla('como-pagas'), ...repetir('tarjeta', empresas)];
  switch (ruta.tipo) {
    case 'servicio':
      return [
        pantalla('viaje'),
        ...(ruta.tieneExtras ? [pantalla('extras')] : []),
        pantalla('contacto'),
        ...pago(1),
      ];
    case 'paquete':
      return [
        pantalla('inicio'),
        ...repetir('servicio', ruta.servicios),
        pantalla('contacto'),
        ...(ruta.conTraslado ? [pantalla('recogida')] : []),
        ...pago(ruta.empresas),
      ];
    case 'traslado':
      return [
        pantalla('tipo'),
        pantalla('fecha'),
        pantalla('hora-pasajeros'),
        pantalla('contacto'),
        pantalla('recogida'),
        ...pago(1),
      ];
  }
}

function indiceDe(pantallas: readonly Pantalla[], id: string): number {
  return pantallas.findIndex((x) => x.id === id);
}

/** La pantalla que sigue a `id`, o `null` en la última (ahí el botón cobra). */
export function siguiente(pantallas: readonly Pantalla[], id: string): string | null {
  const i = indiceDe(pantallas, id);
  return i < 0 ? null : (pantallas[i + 1]?.id ?? null);
}

/** La pantalla previa a `id`, o `null` en la primera (ahí la flecha sale al origen). */
export function anterior(pantallas: readonly Pantalla[], id: string): string | null {
  const i = indiceDe(pantallas, id);
  return i <= 0 ? null : pantallas[i - 1].id;
}

export function pasoDeLaPantalla(pantallas: readonly Pantalla[], id: string): PasoId {
  return pantallas[indiceDe(pantallas, id)]?.paso ?? 'viaje';
}

/** `id` si existe en la ruta; si no (URL vieja, ruta que cambió), la primera pantalla. */
export function pantallaValida(pantallas: readonly Pantalla[], id: string | null | undefined): string {
  return id && indiceDe(pantallas, id) >= 0 ? id : pantallas[0].id;
}

/** Primera pantalla de un paso: así se entra al asistente desde `?paso=`. */
export function primeraDelPaso(pantallas: readonly Pantalla[], paso: PasoId): string {
  return (pantallas.find((x) => x.paso === paso) ?? pantallas[0]).id;
}

/** ¿`a` va antes que `b` en la ruta? Las dos deben existir. */
export function estaAntesDe(pantallas: readonly Pantalla[], a: string, b: string): boolean {
  const ia = indiceDe(pantallas, a);
  const ib = indiceDe(pantallas, b);
  return ia >= 0 && ib >= 0 && ia < ib;
}
