import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/site';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      // El checkout no aporta nada en buscadores y con parametros de fecha
      // genera infinitas variantes de la misma pagina.
      disallow: ['/es/reservar', '/en/reservar'],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
