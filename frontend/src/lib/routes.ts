import type { Locale } from '@/app/[lang]/dictionaries';

function anclaNormalizada(ancla?: string): string {
  if (!ancla) return '';
  return ancla.startsWith('#') ? ancla : `#${ancla}`;
}

export function hrefInicio(lang: Locale, ancla?: string): string {
  return `/${lang}${anclaNormalizada(ancla)}`;
}

export function hrefSede(lang: Locale, slug: string, ancla?: string): string {
  return `/${lang}/sede/${encodeURIComponent(slug)}${anclaNormalizada(ancla)}`;
}

/** La página de un paquete de la sede (F10). La moneda viaja en `?moneda=` solo si no es la de siempre. */
export function hrefDetallePaquete(lang: Locale, sedeSlug: string, paqueteSlug: string, moneda?: 'MXN' | 'USD'): string {
  const ruta = `/${lang}/sede/${encodeURIComponent(sedeSlug)}/paquete/${encodeURIComponent(paqueteSlug)}`;
  return moneda ? `${ruta}?moneda=${moneda}` : ruta;
}
