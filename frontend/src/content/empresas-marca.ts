// La marca de cada empresa (nombre y logo): lo único de `empresas.ts` que necesitan los
// componentes de cliente (la cabecera de la sede, el sello). Sin `server-only` a propósito;
// todo lo demás de la empresa (descripción, reseñas, contacto…) vive en `empresas.ts`, que
// toma de aquí estos dos campos para no duplicarlos.

export type MarcaEmpresa = {
  slug: string;
  nombre: string;
  /** Ruta bajo /public. Sin logo, el sello pinta el monograma de las iniciales. */
  logo?: string;
};

export const MARCAS: readonly MarcaEmpresa[] = [
  { slug: 'sal-y-sol', nombre: 'Sal y Sol Sportfishing', logo: '/logos/logo2salysol.webp' },
  { slug: 'transporte-la-paz', nombre: 'DLS Transporte' },
  { slug: 'la-ventana-travel', nombre: 'La Ventana Travel' },
  { slug: 'piratas-adventures', nombre: 'Piratas Adventures' },
];

export function marcaDe(slug: string | null | undefined): MarcaEmpresa | undefined {
  return slug ? MARCAS.find((marca) => marca.slug === slug) : undefined;
}
