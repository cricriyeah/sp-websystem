// frontend/src/lib/booking-href.ts
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import type { Origen } from './origen';

type ServicioEnlace = Pick<ServicioCatalogo, 'slug' | 'empresa_slug' | 'tipo_servicio'>;

function rutaConQuery(ruta: string, params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor) query.set(clave, valor);
  }
  const serializada = query.toString();
  return serializada ? `${ruta}?${serializada}` : ruta;
}

/**
 * `origen`: a dónde regresa «salir» en el primer paso de la reserva. Sin él vuelve a la sede
 * (`lib/origen.ts`); solo hace falta cuando el enlace nace en otra página (p. ej. el servicio).
 */
export function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda, origen?: Origen): string {
  const query = new URLSearchParams({ paquete: paquete.slug });
  if (paquete.sede_slug) query.set('sede', paquete.sede_slug);
  query.set('moneda', moneda);
  if (origen) query.set('origen', origen);
  return `/${lang}/reservar?${query.toString()}`;
}

type OpcionesEnlace = { origen?: Origen; sede?: string };

export function hrefServicio(servicio: ServicioEnlace, lang: Locale, moneda: Moneda, opciones: OpcionesEnlace = {}): string {
  if (servicio.tipo_servicio === 'transporte') {
    return rutaConQuery(`/${lang}/traslados`, {
      empresa: servicio.empresa_slug,
      moneda,
      sede: opciones.sede,
      origen: opciones.origen,
    });
  }
  return rutaConQuery(`/${lang}/reservar`, {
    servicio: servicio.slug,
    empresa: servicio.empresa_slug,
    moneda,
    sede: opciones.sede,
    origen: opciones.origen,
  });
}

export function hrefDetalleServicio(
  servicio: Pick<ServicioCatalogo, 'slug' | 'empresa_slug'>,
  lang: Locale,
  moneda: Moneda,
  sedeSlug?: string,
): string {
  return rutaConQuery(
    `/${lang}/servicio/${encodeURIComponent(servicio.empresa_slug)}/${encodeURIComponent(servicio.slug)}`,
    { sede: sedeSlug, moneda },
  );
}
