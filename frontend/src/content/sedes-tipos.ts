// frontend/src/content/sedes-tipos.ts
//
// Solo tipos: sin runtime, sin valores exportados. Un `import type` de este
// archivo se borra por completo en compilacion, asi que es seguro importarlo
// desde cualquier lado (Client o Server Component) sin costo de bundle.

/**
 * Lo minimo que un Client Component necesita por sede. Nombre, logo, sitio y redes de la
 * empresa protagonista NO viven aqui: salen de `empresas-marca.ts` / `empresas.ts`.
 */
export type SedeIndiceEntry = {
  slug: string;
  nombre: string;
  /**
   * La empresa local con la que Sun Baja Experience hace esta sede: da nombre y logo a la
   * segunda marca de la cabecera y al sello del arranque. Sin ella, ninguna de las dos.
   */
  empresaProtagonistaSlug?: string;
};

export type SedeHeroContenido = {
  video: string | null;
  imagen: string | null;
  /** `object-position` para encuadrar la foto/video de esta sede; sin él, centrado. */
  posicionImagen?: string;
  /** Foto de la cortina del hub, si debe ser otra que `imagen` (p. ej. cuando el texto blanco no se lee sobre el póster). */
  imagenCortina?: string;
  /** `object-position` solo bajo 640 px (el encuadre del móvil); sin él vale `posicionImagen`. */
  posicionImagenMovil?: string;
  /** `object-position` del video solo bajo 640 px; sin él vale `posicionImagenMovil`. */
  posicionVideoMovil?: string;
  /** Las palabras gigantes que rotan en el arranque. Sin ellas salen del catálogo (una por tipo de servicio),
   * y una sede con un solo tipo se queda quieta. */
  palabras?: string[];
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
  etiquetaCalendario: string;
  etiquetaFuerte: string;
  etiquetaOtras: string;
  filas: {
    periodo: string;
    meses: string[];
    estrella: string;
    /** Otras especies de la temporada; vacío si la fila es solo la estrella. */
    otras: string;
    /** Una frase bajo el título de la temporada: qué esperar. */
    descripcion: string;
    /** La foto estrella de la temporada. */
    foto: string;
    /** La temporada fuerte lleva la etiqueta y su tramo del año relleno. */
    fuerte: boolean;
  }[];
};

/** «Tu día»: los momentos de un viaje de la sede, en orden. Las fotos son decorativas (la palabra y la frase lo dicen). */
export type SedeDia = {
  titulo: string;
  /** Nombre accesible de la fila. */
  etiqueta: string;
  momentos: { titulo: string; texto: string; foto: string }[];
};

/**
 * «Conócenos»: la gente detrás de los servicios de la sede. El título, una apertura corta, una sola foto con dos cifras
 * al lado (lo que sí se sabe: los años de Rogelio en el mar y las generaciones de su familia), los socios (nombre y una
 * línea cada uno), el gremio de capitanes (nombre y foto, sin más datos), la flota (tres fotos de las pangas) y el cierre
 * (una cita con su fuente y el botón de reservar).
 */
export type SedeConocenos = {
  /** El título en tres líneas; la del medio es la que se destaca («generaciones»). */
  titulo: { inicio: string; destacada: string; fin: string };
  apertura: string;
  foto: { src: string; alt: string };
  /** Dos cifras que el dueño confirmó, junto a la foto: `valor` en grande y `texto` que dice de quién son. */
  cifras: { valor: string; texto: string }[];
  socios: { nombre: string; texto: string }[];
  /**
   * El gremio de capitanes locales: un círculo con aro de sol por capitán (nombre y, si hay, foto). Un capitán
   * `pendiente` es relleno y no se publica (`capitanesVisibles`); sin ninguno visible el bloque no se pinta.
   */
  gremio: {
    titulo: string;
    texto: string;
    capitanes: { nombre: string; foto?: string; alt?: string; pendiente?: boolean }[];
  };
  /** Las pangas: tres fotos en vertical con un solo pie común. */
  flota: { pie: string; fotos: { src: string; alt: string }[] };
  cita: { texto: string; atribucion: string };
  /** El texto del botón con que cierra la sección (lleva a lo que se puede reservar). */
  reservar: string;
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
  /** El día del viaje, momento por momento. Sin él, no hay sección. */
  dia?: SedeDia;
  /** Quiénes hacen los servicios de la sede. Sin él, no hay sección. */
  conocenos?: SedeConocenos;
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
