import type { MetadataRoute } from 'next';
import { LOCALES, RUTAS, absolutaEn } from '@/lib/site';

/**
 * Una entrada por pagina y por idioma, cada una declarando su alternativa en el
 * otro idioma para que Google no las tome por contenido duplicado.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const ahora = new Date();

  return LOCALES.flatMap((lang) =>
    RUTAS.filter((ruta) => ruta !== '/reservar').map((ruta) => ({
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
    }))
  );
}
