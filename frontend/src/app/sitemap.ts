import type { MetadataRoute } from 'next';
import { LOCALES, rutasEstaticas, rutasPaquetes, rutasSedes, rutasServicios, absolutaEn } from '@/lib/site';

// Sin `lastModified`: no hay una fecha real de cambio por página, y poner «ahora» en cada entrada hace que
// Google deje de creerle a todas las fechas del sitemap.
function entradaDe(lang: (typeof LOCALES)[number], ruta: string) {
  return {
    url: absolutaEn(lang, ruta),
    changeFrequency: ruta === '' ? ('weekly' as const) : ('yearly' as const),
    priority: ruta === '' ? 1 : 0.5,
    alternates: {
      languages: {
        'es-MX': absolutaEn('es', ruta),
        'en-US': absolutaEn('en', ruta),
        // El mismo `x-default` que las etiquetas de cada página: HTML y sitemap tienen que decir lo mismo.
        'x-default': absolutaEn('es', ruta),
      },
    },
  };
}

/**
 * Una entrada por pagina y por idioma. Las rutas de sede, de paquete y de servicio se
 * agregan por idioma a partir de una sola lista reconciliada (el índice no varía por idioma).
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const estaticas = LOCALES.flatMap((lang) =>
    rutasEstaticas.filter((ruta) => ruta !== '/reservar').map((ruta) => entradaDe(lang, ruta)),
  );

  const [sedes, paquetes, servicios] = await Promise.all([rutasSedes(), rutasPaquetes(), rutasServicios()]);
  const deSede = LOCALES.flatMap((lang) =>
    [...sedes, ...paquetes, ...servicios].map((ruta) => entradaDe(lang, ruta)),
  );

  return [...estaticas, ...deSede];
}
