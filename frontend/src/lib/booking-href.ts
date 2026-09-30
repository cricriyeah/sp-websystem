// frontend/src/lib/booking-href.ts
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';

type ServicioEnlace = Pick<ServicioCatalogo, 'slug' | 'empresa_slug' | 'tipo_servicio'>;

function rutaConQuery(ruta: string, params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor) query.set(clave, valor);
  }
  const serializada = query.toString();
  return serializada ? `${ruta}?${serializada}` : ruta;
}

export function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): string {
  const query = new URLSearchParams({ paquete: paquete.slug });
  if (paquete.sede_slug) query.set('sede', paquete.sede_slug);
  query.set('moneda', moneda);
  return `/${lang}/reservar?${query.toString()}`;
}

export function hrefServicio(servicio: ServicioEnlace, lang: Locale, moneda: Moneda): string {
  if (servicio.tipo_servicio === 'transporte') {
    return rutaConQuery(`/${lang}/traslados`, {
      empresa: servicio.empresa_slug,
      moneda,
    });
  }
  return rutaConQuery(`/${lang}/reservar`, {
    servicio: servicio.slug,
    empresa: servicio.empresa_slug,
    moneda,
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
