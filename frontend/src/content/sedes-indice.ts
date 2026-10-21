// frontend/src/content/sedes-indice.ts
//
// Client-safe de verdad: SiteHeader (Client Component, montado en cada
// pagina) importa esto para resolver marca/logo cuando no hay slug de sede
// en la URL. El contenido largo (hero completo, colaboracion, otras
// empresas, negocio) vive en `sedes-cuerpo.ts` (server-only) para que nunca
// termine en el bundle de cliente.
import type { SedeIndiceEntry } from './sedes-tipos';

export const SEDES_INDICE: Record<string, SedeIndiceEntry> = {
  'la-paz': {
    slug: 'la-paz',
    nombre: 'La Paz',
    empresaProtagonistaSlug: 'sal-y-sol',
  },
  'la-ventana': {
    slug: 'la-ventana',
    nombre: 'La Ventana',
    empresaProtagonistaSlug: 'la-ventana-travel',
  },
  'puerto-chale': {
    slug: 'puerto-chale',
    nombre: 'Puerto Chale',
    empresaProtagonistaSlug: 'piratas-adventures',
  },
};

/** @public Lo usan las pruebas. */
export const SLUGS_CON_CONTENIDO: string[] = Object.keys(SEDES_INDICE);

export function getSedeIndice(slug: string): SedeIndiceEntry | undefined {
  return Object.hasOwn(SEDES_INDICE, slug) ? SEDES_INDICE[slug] : undefined;
}
