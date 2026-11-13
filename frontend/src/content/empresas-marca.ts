// La marca de cada empresa (nombre y logo): lo único de `empresas.ts` que necesitan los
// componentes de cliente (la cabecera de la sede, el sello). Sin `server-only` a propósito;
// todo lo demás de la empresa (descripción, reseñas, contacto…) vive en `empresas.ts`, que
// toma de aquí estos dos campos para no duplicarlos.

/** `blanco`: el mismo logo todo en blanco, para ir sobre el video del héroe (el de color no se lee ahí). */
/**
 * `barra`: el alto en la barra de arriba, si no es el de Sal y Sol. Un logo de solo letras (Piratas) pesa más que uno
 * con isotipo a la misma altura (dueño, 2026-11-12: se veía demasiado grande).
 *
 * `sello`: el alto como sello de esquina de una sección, si no es el de Sal y Sol (Piratas, de puras letras, más bajo).
 *
 * `secciones`: en qué secciones de la sede va el logo largo como sello de esquina. Sin él, solo en Temporadas (Sal y
 * Sol). Piratas (dueño, 2026-11-12) lo lleva en la galería y en Temporadas usa su escudo (`logo`, PNG).
 */
export type LogoLargo = { src: string; ancho: number; alto: number; blanco?: string; barra?: string; sello?: string; secciones?: ('temporadas' | 'galeria')[] };

export type MarcaEmpresa = {
  slug: string;
  nombre: string;
  /**
   * La sede donde opera. Vive aquí y no en `empresas.ts` (server-only) porque también la lee
   * `proxy.ts`: un link directo al checkout de una empresa pasa el modo «solo sede» a su sede.
   */
  sede: string;
  /** Ruta bajo /public. Sin logo, el sello pinta el monograma de las iniciales. */
  logo?: string;
  /** Solo el símbolo, sin letras: para la barra de arriba, donde el nombre ya va en el texto alternativo. */
  simbolo?: string;
  /** El símbolo sin fondo y recortado a su contorno, para la barra de arriba (blanca): así llena la altura. */
  simboloBarra?: string;
  /** En el arranque de la sede el logo va suelto, sin el círculo del sello: solo si el logo ya trae su propio disco. */
  heroSinCirculo?: boolean;
  /** El logo dibujado en blanco, de un solo color: va de fondo, muy tenue, en la banda tinta de «Reserva con tranquilidad». */
  ilustracionFondo?: string;
  /**
   * El logo largo a color (isotipo y nombre), con la proporción de su viewBox para que reserve su alto antes de cargar:
   * en la esquina de «Las pangas» y al cierre de «Conócenos», encima del botón de reservar.
   */
  logoLargo?: LogoLargo;
  /** El logo de la tarjeta «Quién te lleva» cuando no es `logo` (Sal y Sol: el logo largo nuevo, 2026-11-07). */
  logoTarjeta?: string;
};

export const MARCAS: readonly MarcaEmpresa[] = [
  { slug: 'sal-y-sol', sede: 'la-paz', nombre: 'Sal y Sol Sportfishing', logo: '/logos/salysol.webp', simbolo: '/logos/salysol.webp', simboloBarra: '/logos/salysol-barra.webp', heroSinCirculo: true, ilustracionFondo: '/logos/logosbgsalysol.svg', logoLargo: { src: '/logos/salysol-largo.svg', blanco: '/logos/salysol-largo-blanco.svg', ancho: 3846, alto: 1733 }, logoTarjeta: '/logos/salysol-largo.svg' },
  { slug: 'transporte-la-paz', sede: 'la-paz', nombre: 'DLS Transporte', logo: '/logos/dlstransporte.webp' },
  { slug: 'la-ventana-travel', sede: 'la-ventana', nombre: 'La Ventana Travel', logo: '/logos/laventanatravel-oscuro.webp', simbolo: '/logos/laventanatravel-simbolo.webp' },
  // Logo largo nuevo de Piratas (dueño, 2026-11-12): en la barra, el héroe, Temporadas y el cierre de «Conócenos».
  { slug: 'piratas-adventures', sede: 'puerto-chale', nombre: 'Piratas Adventures', logo: '/logos/piratasadventures.webp', logoLargo: { src: '/logos/piratas-largo.svg', blanco: '/logos/piratas-largo-blanco.svg', ancho: 1105, alto: 325, barra: 'h-7 sm:h-8', sello: 'h-9 sm:h-11 lg:h-12 xl:h-14', secciones: ['galeria'] } },
];
