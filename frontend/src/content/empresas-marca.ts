// La marca de cada empresa (nombre y logo): lo único de `empresas.ts` que necesitan los
// componentes de cliente (la cabecera de la sede, el sello). Sin `server-only` a propósito;
// todo lo demás de la empresa (descripción, reseñas, contacto…) vive en `empresas.ts`, que
// toma de aquí estos dos campos para no duplicarlos.

export type MarcaEmpresa = {
  slug: string;
  nombre: string;
  /** Ruta bajo /public. Sin logo, el sello pinta el monograma de las iniciales. */
  logo?: string;
  /**
   * Versión del logo sin fondo, para ponerla sobre un campo de color propio (tablero de empresas).
   * Sin ella, `logo` sirve para los dos usos. El de La Ventana Travel es blanco: `logo` lo trae dentro
   * de un disco oscuro para verse en los sellos circulares blancos.
   */
  logoLibre?: string;
  /** Campo de color de su bloque en el tablero de empresas (F10): el que deja verse a su logo y dice qué hace. */
  campo: 'cafe-claro' | 'coral' | 'verde' | 'azul';
};

export const MARCAS: readonly MarcaEmpresa[] = [
  { slug: 'sal-y-sol', nombre: 'Sal y Sol Sportfishing', logo: '/logos/logo2salysol.webp', campo: 'cafe-claro' },
  { slug: 'transporte-la-paz', nombre: 'DLS Transporte', logo: '/logos/dlstransporte.webp', campo: 'coral' },
  { slug: 'la-ventana-travel', nombre: 'La Ventana Travel', logo: '/logos/laventanatravel-sello.webp', logoLibre: '/logos/laventanatravel.webp', campo: 'verde' },
  { slug: 'piratas-adventures', nombre: 'Piratas Adventures', logo: '/logos/piratasadventures.webp', campo: 'azul' },
];

export function marcaDe(slug: string | null | undefined): MarcaEmpresa | undefined {
  return slug ? MARCAS.find((marca) => marca.slug === slug) : undefined;
}
