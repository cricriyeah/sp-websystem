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
  /** Qué se ve en la foto (o el póster del video), para lectores de pantalla y buscadores de imágenes. */
  alt?: string;
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
 * una persona. Un título, una frase de apertura grande, los párrafos del relato y una foto del equipo; la
 * tripulación como cartel (un capitán `pendiente` no se publica, `capitanesVisibles`); y el cierre: el logo largo y el botón.
 */
export type SedeConocenos = {
  titulo: string;
  apertura: string;
  historia: string[];
  /** Una foto del equipo o del gremio, nunca el retrato de una sola persona. */
  foto: { src: string; alt: string };
  /** Dibujo de un solo color (ruta bajo /public y su proporción) que va de fondo, grande y muy tenue, detrás del relato. */
  ilustracion?: { src: string; ancho: number; alto: number };
  /** Lo primero de la sección, grande: el año del gremio y su texto (pedido del dueño, 2026-11-04). */
  desde?: { texto: string; anio: string };
  /** Los capitanes del gremio: sus nombres van como una frase dentro del relato, tras el párrafo que los presenta. */
  tripulacion: {
    /** Título que encabeza la frase de nombres («STAFF DE CAPITANES»; pedido del dueño, 2026-11-04). */
    titulo: string;
    /** `apodo` va junto al nombre en la frase, sin comillas; `detalle` (el apellido) no se pinta. */
    capitanes: { nombre: string; apodo?: string; detalle?: string; pendiente?: boolean }[];
    /** «y» o «and»: une al último nombre en la frase de los capitanes. */
    y: string;
    /**
     * Fotos de capitanes que siguen a la foto del relato en su columna: la primera encimada sobre ella y las demás en
     * dos columnas escalonadas (dueño, 2026-11-04). `posicion` es el `object-position` del recorte (por omisión 50% 40%).
     */
    fotos: { src: string; alt: string; posicion?: string }[];
  };
  /** Solo el botón: encima va el logo largo de la empresa (`MarcaEmpresa.logoLargo`), que dice el resto. */
  cierre: { boton: string };
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
 * «Las pangas»: justo bajo el héroe, el título, la foto de la flota completa y, pegado a ella, el texto que nombra cada
 * panga en el orden de la foto; al lado, las pangas navegando. Sin botón: lo siguiente es lo que se reserva.
 */
export type SedePangas = {
  titulo: string;
  /** La flota formada: va completa, en su proporción y sin nada encima. */
  flota: { src: string; alt: string; ancho: number; alto: number };
  /** La frase grande bajo la flota. */
  frase: string;
  /** Las pangas en el orden en que salen en la foto de la flota, de izquierda a derecha. */
  nombres: string[];
  /** «y» o «and» antes del último nombre. */
  y: string;
  /** El párrafo: `{nombres}` se cambia por la lista de las pangas. */
  texto: string;
  /** Las pangas navegando, cada una con lo que muestra. */
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
