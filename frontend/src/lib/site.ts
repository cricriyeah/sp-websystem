import type { Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getPaquetesSede, getServiciosSede, getSedes } from './api';
import { sedesActivas } from './reconciliar-sedes';

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

/** Rutas publicas estaticas del sitio (no dependen de que sedes esten activas). */
export const rutasEstaticas = ['', '/reservar', '/deslinde', '/privacidad', '/nosotros'] as const;

/**
 * Keep the sitemap, hub and navigation on the same active destination list.
 */
export async function rutasSedes(): Promise<string[]> {
  const sedesApi = await getSedes().catch(() => null);
  return sedesActivas(SEDES_INDICE, sedesApi).map((sede) => `/sede/${sede.slug}`);
}

/** Las páginas de paquete de las sedes activas. Si el catálogo de una sede no responde, esa sede no aporta rutas. */
export async function rutasPaquetes(): Promise<string[]> {
  const sedesApi = await getSedes().catch(() => null);
  const sedes = sedesActivas(SEDES_INDICE, sedesApi);
  const porSede = await Promise.all(
    sedes.map(async (sede) => {
      const paquetes = await getPaquetesSede(sede.slug).catch(() => []);
      return paquetes.map((paquete) => `/sede/${sede.slug}/paquete/${paquete.slug}`);
    }),
  );
  return porSede.flat();
}

/**
 * Las páginas de servicio de las sedes activas (pesca, ballenas, traslados…): son lo que la gente busca y lo
 * que se reserva, y no estaban en el sitemap. Si el catálogo de una sede no responde, esa sede no aporta rutas.
 */
export async function rutasServicios(): Promise<string[]> {
  const sedesApi = await getSedes().catch(() => null);
  const sedes = sedesActivas(SEDES_INDICE, sedesApi);
  const porSede = await Promise.all(
    sedes.map(async (sede) => {
      const servicios = await getServiciosSede(sede.slug).catch(() => []);
      return servicios.map((servicio) => `/servicio/${servicio.empresa_slug}/${servicio.slug}`);
    }),
  );
  return [...new Set(porSede.flat())];
}

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
