// frontend/src/content/sedes-tipos.ts
//
// Solo tipos: sin runtime, sin valores exportados. Un `import type` de este
// archivo se borra por completo en compilacion, asi que es seguro importarlo
// desde cualquier lado (Client o Server Component) sin costo de bundle.
import type { Locale } from '@/app/[lang]/dictionaries';

export type { Locale };

/**
 * Lo minimo que un Client Component necesita por sede. Nombre, logo, sitio y redes de la
 * empresa protagonista NO viven aqui: salen de `empresas-marca.ts` / `empresas.ts`.
 */
export type SedeIndiceEntry = {
  slug: string;
  nombre: string;
  /**
   * La empresa local con la que Sun Baja Experience hace esta sede: da nombre y logo a la
   * segunda marca de la cabecera y a la frase de colaboracion. Sin ella, ninguna de las dos.
   */
  empresaProtagonistaSlug?: string;
};

export type SedeHeroContenido = {
  video: string | null;
  imagen: string | null;
  /** `object-position` para encuadrar la foto/video de esta sede; sin él, centrado. */
  posicionImagen?: string;
  titulo: { start: string; emphasis: string; end: string };
  subtitulo: string;
  facts: { value: string; label: string }[];
};

export type SedeNegocio = {
  nombre: string;
  calle: string;
  ciudad: string;
  estado: string;
  pais: string;
  horarioApertura: string;
  horarioCierre: string;
} | null;

/** El calendario de especies de una sede: una fila por temporada, en orden de temporada. */
export type SedeTemporadas = {
  intro: string;
  nota: string;
  etiquetaCalendario: string;
  etiquetaFuerte: string;
  etiquetaOtras: string;
  filas: {
    periodo: string;
    meses: string[];
    estrella: string;
    otras: string;
    nota: string;
    /** La foto estrella de la temporada. */
    foto: string;
    /** La temporada fuerte lleva la etiqueta y su tramo del año relleno. */
    fuerte: boolean;
  }[];
};

export type SedeDestacada = {
  tipo: 'servicio' | 'paquete';
  slug: string;
  empresaSlug?: string;
  inlineable: boolean;
};

export type SedeServicioTransporte = {
  empresaSlug: string;
} | null;

/** Contenido largo/pesado por sede — vive en `sedes-cuerpo.ts` (server-only). */
export type SedeCuerpoContenido = {
  slug: string;
  /** Igual que en el indice (ver `SedeIndiceEntry`). */
  empresaProtagonistaSlug?: string;
  negocio: SedeNegocio;
  metaTitle: string;
  metaDescription: string;
  hero: SedeHeroContenido;
  destacadas: SedeDestacada[];
  /** Slugs de las demas empresas de la sede; sus datos salen de `empresas.ts`. */
  otrasEmpresas: string[];
  servicioTransporte: SedeServicioTransporte;
  /** Galeria propia de la sede (con medidas, para `fotosAptas`). Sin ella, no hay seccion. */
  galeria?: { src: string; alt: string; ancho: number; alto: number; empresaSlug: string }[];
  temporadas?: SedeTemporadas;
  faq?: { q: string; a: string }[];
};

/**
 * Forma combinada (indice + cuerpo) que usan las paginas de servidor. Solo
 * existe como tipo — el valor lo arma `getSedeContenido()` en
 * `sedes-cuerpo.ts` (server-only), nunca se construye desde un Client
 * Component.
 */
export type SedeContenido = SedeIndiceEntry & SedeCuerpoContenido;
