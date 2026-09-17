import type { MetadataRoute } from 'next';
import { LOCALES, rutasEstaticas, rutasSedes, absolutaEn } from '@/lib/site';

function entradaDe(lang: (typeof LOCALES)[number], ruta: string, ahora: Date) {
  return {
    url: absolutaEn(lang, ruta),
    lastModified: ahora,
    changeFrequency: ruta === '' ? ('weekly' as const) : ('yearly' as const),
    priority: ruta === '' ? 1 : 0.5,
    alternates: {
      languages: {
        'es-MX': absolutaEn('es', ruta),
        'en-US': absolutaEn('en', ruta),
      },
    },
  };
}

/**
 * Una entrada por pagina y por idioma. Las rutas de sede se agregan por
 * idioma a partir de una sola lista reconciliada (el índice no varía por idioma).
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const ahora = new Date();

  const estaticas = LOCALES.flatMap((lang) =>
    rutasEstaticas.filter((ruta) => ruta !== '/reservar').map((ruta) => entradaDe(lang, ruta, ahora)),
  );

  const rutas = await rutasSedes();
  const deSede = LOCALES.flatMap((lang) =>
    rutas.map((ruta) => entradaDe(lang, ruta, ahora)),
  );

  return [...estaticas, ...deSede];
}
