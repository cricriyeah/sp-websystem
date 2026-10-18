// A dónde lleva «salir» desde el primer paso de una reserva: el origen explícito
// (`?origen=`) si es un destino conocido y, si falta, la página de la sede.

export type Origen = 'sede' | 'servicio' | 'portada';

export type EntradaOrigen = {
  lang: string;
  /** Valor crudo de `?origen=` (sede, servicio o portada); cualquier otro se ignora. */
  origen?: string | null;
  sedeSlug?: string | null;
  /** Ruta de la página del servicio o del paquete (sin idioma), p. ej. `servicio/sal-y-sol/pesca`. */
  rutaServicio?: string | null;
};

export function origenValido(valor: string | null | undefined): Origen | null {
  return valor === 'sede' || valor === 'servicio' || valor === 'portada' ? valor : null;
}

export function hrefDeOrigen({ lang, origen, sedeSlug, rutaServicio }: EntradaOrigen): string {
  const portada = `/${lang}`;
  const sede = sedeSlug ? `/${lang}/sede/${sedeSlug}` : portada;
  switch (origenValido(origen)) {
    case 'portada':
      return portada;
    case 'servicio':
      return rutaServicio ? `/${lang}/${rutaServicio.replace(/^\/+/, '')}` : sede;
    default:
      return sede;
  }
}
