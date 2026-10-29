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
 * «Conócenos»: la historia de la gente detrás de los servicios de la sede, contada como relato (nada de cifras sueltas:
 * el dueño las leyó como estadísticas de ventas). El protagonista es el grupo (la familia y el gremio de capitanes), no
 * una persona. Un título, una frase de apertura grande, los párrafos del relato y una foto del equipo; la prensa; la
 * tripulación como cartel (un capitán `pendiente` no se publica, `capitanesVisibles`); y el cierre con el botón.
 */
export type SedeConocenos = {
  titulo: string;
  apertura: string;
  historia: string[];
  /** Una foto del equipo o del gremio, nunca el retrato de una sola persona. */
  foto: { src: string; alt: string };
  prensa: { etiqueta: string; texto: string; fuente: string };
  tripulacion: {
    titulo: string;
    texto: string;
    capitanes: { nombre: string; detalle?: string; pendiente?: boolean }[];
  };
  cierre: { titulo: string; frase: string; boton: string };
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

/**
 * «Nuestras pangas»: justo bajo el héroe, la firma de la empresa (su isotipo con el nombre), un título, una frase y tres
 * fotos (una protagonista y dos de apoyo), cada una con lo que muestra. Sin botón: lo siguiente es lo que se reserva.
 */
export type SedePangas = {
  titulo: string;
  texto: string;
  fotos: { src: string; alt: string; pie: string }[];
};

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
  /** Las pangas de la sede, bajo el héroe. Sin ellas, no hay sección. */
  pangas?: SedePangas;
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
