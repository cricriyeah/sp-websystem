// Cómo se etiqueta y se acomoda el catálogo de una sede y del hub, sin React: familia de
// actividad, chip, base de cobro, si hay foto o galería y la plantilla de cada grupo de
// tarjetas. Las vistas solo pintan lo que esto decide.

type Lang = 'es' | 'en';

/** Familia de actividad (color del chip). Hospedaje, traslados y paquetes mixtos no tienen. */
export type Actividad = 'mar' | 'ciudad' | 'outside';

type ServicioEtiquetable = { slug: string; tipo_servicio: string };
type PaqueteEtiquetable = { servicios_asociados: { servicio: ServicioEtiquetable }[] };

/**
 * Paseos que NO son de mar, por slug. Hoy todos los paseos del catálogo (avistamientos, safari
 * marino) son de mar: el mapa queda vacío y el valor por defecto es `mar`.
 */
const ACTIVIDAD_POR_SERVICIO: Record<string, Actividad> = {};

export function actividadDe(servicio: ServicioEtiquetable): Actividad | null {
  if (servicio.tipo_servicio === 'pesca') return 'mar';
  if (servicio.tipo_servicio === 'paseo') return ACTIVIDAD_POR_SERVICIO[servicio.slug] ?? 'mar';
  return null;
}

/** La actividad común de todos sus servicios, o null si difieren (o no tiene). */
export function actividadDePaquete(paquete: PaqueteEtiquetable): Actividad | null {
  const familias = new Set(paquete.servicios_asociados.map((c) => actividadDe(c.servicio)));
  if (familias.size !== 1) return null;
  return [...familias][0];
}

const BASES: Record<string, Record<Lang, string>> = {
  por_persona: { es: 'por persona', en: 'per person' },
  por_grupo: { es: 'por grupo', en: 'per group' },
  por_noche: { es: 'por noche', en: 'per night' },
  tarifa_fija: { es: 'tarifa fija', en: 'flat rate' },
  por_ruta: { es: 'según ruta', en: 'by route' },
};

/** Junto al precio: «desde $X por persona». No existe «por barco» en el backend. */
export function baseDeCobro(estrategia: string, lang: Lang): { texto: string; conDesde: boolean } | null {
  const base = BASES[estrategia];
  // Según ruta no lleva «desde»: el precio depende de la ruta, no hay un mínimo que anunciar.
  return base ? { texto: base[lang], conDesde: estrategia !== 'por_ruta' } : null;
}

export type Chip = { tipo: Actividad | 'neutro'; icono?: 'hospedaje' | 'traslado' | 'paquete'; texto: string };

const PALABRA: Record<string, Record<Lang, string>> = {
  pesca: { es: 'Pesca', en: 'Fishing' },
  paseo: { es: 'Paseos', en: 'Tours' },
  hospedaje: { es: 'Hospedaje', en: 'Lodging' },
  transporte: { es: 'Traslados', en: 'Transfers' },
  bajo_demanda: { es: 'Paseos', en: 'Tours' },
  paquete: { es: 'Paquetes', en: 'Packages' },
};

const ICONO: Record<string, Chip['icono']> = { hospedaje: 'hospedaje', transporte: 'traslado' };

export function chipDeServicio(servicio: ServicioEtiquetable, lang: Lang): Chip {
  const texto = (PALABRA[servicio.tipo_servicio] ?? PALABRA.paseo)[lang];
  const actividad = actividadDe(servicio);
  if (actividad) return { tipo: actividad, texto };
  return { tipo: 'neutro', icono: ICONO[servicio.tipo_servicio] ?? 'paquete', texto };
}

export function chipDePaquete(paquete: PaqueteEtiquetable, lang: Lang): Chip {
  const actividad = actividadDePaquete(paquete);
  const texto = PALABRA.paquete[lang];
  return actividad ? { tipo: actividad, texto } : { tipo: 'neutro', icono: 'paquete', texto };
}

const ORDEN_SEDE = ['pesca', 'paseo', 'hospedaje', 'transporte', 'paquete'];

/** Tarjeta de sede del hub: hasta 3 chips, sin repetir, en orden fijo. */
export function chipsDeSede(servicios: ServicioEtiquetable[], paquetes: PaqueteEtiquetable[], lang: Lang): Chip[] {
  const tipos = new Set(servicios.map((s) => (s.tipo_servicio === 'bajo_demanda' ? 'paseo' : s.tipo_servicio)));
  if (paquetes.length > 0) tipos.add('paquete');
  return ORDEN_SEDE.filter((tipo) => tipos.has(tipo)).slice(0, 3).map((tipo) =>
    tipo === 'paquete'
      ? { tipo: 'neutro' as const, icono: 'paquete' as const, texto: PALABRA.paquete[lang] }
      : chipDeServicio({ slug: '', tipo_servicio: tipo }, lang),
  );
}

/** Las tarjetas de sede del hub llevan foto solo si TODAS tienen una propia (no una ilustración). */
export function tarjetasConFoto(sedes: { hero: { imagen: string | null } }[]): boolean {
  return sedes.length > 0 && sedes.every(({ hero }) => Boolean(hero.imagen) && !hero.imagen!.startsWith('/ilustraciones/'));
}

type Medida = { ancho: number; alto: number };
const ladoLargo = ({ ancho, alto }: Medida) => Math.max(ancho, alto);

/** Fuera las fotos con el lado largo menor de 800 px: se verían borrosas. */
export function fotosAptas<T extends Medida>(fotos: T[]): T[] {
  return fotos.filter((foto) => ladoLargo(foto) >= 800);
}

export const aptaParaSlotGrande = (foto: Medida): boolean => ladoLargo(foto) >= 1200;

/** Héroe a 1440 px: con menos de 1600 de ancho se amplía (solo con `object-position` y el visto bueno del dueño). */
export const aptaParaHeroe = (foto: Medida): boolean => foto.ancho >= 1600;

/** Con menos de 3 fotos aptas no hay galería. */
export const hayGaleria = (fotos: Medida[]): boolean => fotosAptas(fotos).length >= 3;

export type PlantillaGrupo = { columnas: 1 | 2 | 3; destacada: 'ninguna' | 'horizontal' | 'cuadrada' | 'ancha' };

/**
 * Cómo se acomoda un grupo de n tarjetas sin celdas vacías: 1 ancha horizontal (máx. 720);
 * 2 en dos columnas; 3 con una destacada de 2×2 y dos al lado; 4 en 2×2; 5 con una destacada
 * de dos columnas + 1, luego 1+1+1; 6 o más en tres columnas.
 */
export function plantillaDeGrupo(n: number): PlantillaGrupo {
  if (n <= 1) return { columnas: 1, destacada: 'horizontal' };
  if (n === 2 || n === 4) return { columnas: 2, destacada: 'ninguna' };
  if (n === 3) return { columnas: 3, destacada: 'cuadrada' };
  if (n === 5) return { columnas: 3, destacada: 'ancha' };
  return { columnas: 3, destacada: 'ninguna' };
}
