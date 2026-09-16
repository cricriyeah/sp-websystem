// frontend/src/content/sedes-tipos.ts
//
// Solo tipos: sin runtime, sin valores exportados. Un `import type` de este
// archivo se borra por completo en compilacion, asi que es seguro importarlo
// desde cualquier lado (Client o Server Component) sin costo de bundle.
import type { Locale } from '@/app/[lang]/dictionaries';

export type { Locale };

/** Lo minimo que un Client Component necesita para resolver marca/logo por sede. */
export type SedeIndiceEntry = {
  slug: string;
  nombre: string;
  empresaFundadoraNombre: string;
  /** Ruta del logo de la empresa fundadora, o `null` para el wordmark generico de agencia. */
  logo: string | null;
};

export type SedeHeroContenido = {
  video: string | null;
  imagen: string | null;
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

export type SedeColaboracion = {
  titulo: string;
  texto1: string;
  texto2: string;
  imagenSrc: string;
  imagenAlt: string;
};

export type SedeDestacada = {
  tipo: 'servicio' | 'paquete';
  slug: string;
  empresaSlug?: string;
  inlineable: boolean;
};

export type SedeOtraEmpresa = {
  slug: string;
  nombre: string;
  descripcion: string;
  enlaceExterno: string;
};

export type SedeServicioTransporte = {
  empresaSlug: string;
  hrefTraslados: string;
} | null;

/** Contenido largo/pesado por sede — vive en `sedes-cuerpo.ts` (server-only). */
export type SedeCuerpoContenido = {
  slug: string;
  empresaFundadoraSlug: string;
  negocio: SedeNegocio;
  metaTitle: string;
  metaDescription: string;
  hero: SedeHeroContenido;
  colaboracion: SedeColaboracion;
  destacadas: SedeDestacada[];
  otrasEmpresas: SedeOtraEmpresa[];
  servicioTransporte: SedeServicioTransporte;
};

/**
 * Forma combinada (indice + cuerpo) que usan las paginas de servidor. Solo
 * existe como tipo — el valor lo arma `getSedeContenido()` en
 * `sedes-cuerpo.ts` (server-only), nunca se construye desde un Client
 * Component.
 */
export type SedeContenido = SedeIndiceEntry & SedeCuerpoContenido;
