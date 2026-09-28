// frontend/src/lib/booking-href.ts
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';

export function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): string {
  const query = new URLSearchParams({ paquete: paquete.slug });
  if (paquete.sede_slug) query.set('sede', paquete.sede_slug);
  query.set('moneda', moneda);
  return `/${lang}/reservar?${query.toString()}`;
}

export function hrefServicio(servicio: ServicioCatalogo, lang: Locale, moneda: Moneda): string {
  return `/${lang}/reservar?servicio=${servicio.slug}&empresa=${servicio.empresa_slug}&moneda=${moneda}`;
}
