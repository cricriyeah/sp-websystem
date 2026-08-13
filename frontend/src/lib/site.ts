import type { Locale } from '@/app/[lang]/dictionaries';

// URL publica del sitio. Hace falta para canonicals, hreflang, sitemap y para
// que las imagenes de Open Graph salgan absolutas (las redes no resuelven rutas
// relativas). En Vercel se pone como variable de entorno del proyecto.
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000').replace(
  /\/$/,
  ''
);

export const LOCALES: Locale[] = ['es', 'en'];

/** Codigo de idioma completo, para hreflang y Open Graph. */
export const LOCALE_TAG: Record<Locale, string> = {
  es: 'es-MX',
  en: 'en-US',
};

/** Rutas publicas del sitio, la fuente del sitemap y de los canonicals. */
export const RUTAS = ['', '/reservar', '/deslinde', '/privacidad'] as const;

export const absolutaEn = (lang: Locale, ruta: string = '') => `${SITE_URL}/${lang}${ruta}`;

/**
 * `alternates` para el metadata de Next: canonical de esta pagina y hreflang de
 * la misma pagina en el otro idioma. Sin esto, Google trata /es y /en como
 * contenido duplicado en vez de dos versiones del mismo.
 */
export function alternativasDe(lang: Locale, ruta: string = '') {
  return {
    canonical: absolutaEn(lang, ruta),
    languages: {
      'es-MX': absolutaEn('es', ruta),
      'en-US': absolutaEn('en', ruta),
      'x-default': absolutaEn('es', ruta),
    },
  };
}

// Datos del negocio para el schema local. La direccion es la real del punto de
// encuentro; las coordenadas se dejan fuera a proposito hasta tenerlas exactas:
// un pin mal puesto manda al cliente a otro lado del malecon.
export const NEGOCIO = {
  nombre: 'Sal y Sol Sportfishing',
  calle: 'Marina La Costa, Rangel y Navarro',
  ciudad: 'La Paz',
  estado: 'Baja California Sur',
  pais: 'MX',
};
