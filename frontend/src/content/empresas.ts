import 'server-only';

// Versión mínima: lo que el sello de empresa necesita para pintar logo o monograma.
// La Task 9.0 la amplía sin cambiar estos tres campos. Al ser `server-only`, la lee
// siempre un `page.tsx` o un Server Component; a las vistas de cliente les pasa por
// prop solo `{ nombre, logo }`.

export type Empresa = {
  slug: string;
  nombre: string;
  /** Ruta bajo /public. Sin logo, el sello pinta el monograma de las iniciales. */
  logo?: string;
};

export const EMPRESAS: readonly Empresa[] = [
  { slug: 'sal-y-sol', nombre: 'Sal y Sol Sportfishing', logo: '/logos/logo2salysol.webp' },
  { slug: 'transporte-la-paz', nombre: 'DLS Transporte' },
  { slug: 'la-ventana-travel', nombre: 'La Ventana Travel' },
  { slug: 'piratas-adventures', nombre: 'Piratas Adventures' },
];
