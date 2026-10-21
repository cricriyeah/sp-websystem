// Cómo se etiqueta y se acomoda el catálogo de una sede y del hub, sin React: familia de
// actividad, chip, base de cobro y si hay foto o galería. Las vistas solo pintan lo que esto decide.

type Lang = 'es' | 'en';

/** Familia de actividad (color del chip). Hospedaje, traslados y paquetes mixtos no tienen. */
export type Actividad = 'mar' | 'ciudad' | 'outside';

type ServicioEtiquetable = { slug: string; tipo_servicio: string };

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

const ORDEN_SEDE = ['pesca', 'paseo', 'hospedaje', 'transporte', 'paquete'];

/** Tarjeta de sede del hub: hasta 3 chips, sin repetir, en orden fijo. */
export function chipsDeSede(servicios: ServicioEtiquetable[], paquetes: readonly unknown[], lang: Lang): Chip[] {
  const tipos = new Set(servicios.map((s) => (s.tipo_servicio === 'bajo_demanda' ? 'paseo' : s.tipo_servicio)));
  if (paquetes.length > 0) tipos.add('paquete');
  return ORDEN_SEDE.filter((tipo) => tipos.has(tipo)).slice(0, 3).map((tipo) =>
    tipo === 'paquete'
      ? { tipo: 'neutro' as const, icono: 'paquete' as const, texto: PALABRA.paquete[lang] }
      : chipDeServicio({ slug: '', tipo_servicio: tipo }, lang),
  );
}

/** La palabra de un tipo de servicio («Pesca», «Traslados»…): rotula su bloque de color y el arranque de sede. */
export function palabraDeServicio(tipoServicio: string, lang: Lang): string {
  return (PALABRA[tipoServicio] ?? PALABRA.paseo)[lang];
}

/** La palabra de un paquete: «5 noches» si trae estancia, «Paquetes» si no. */
export function palabraDePaquete(noches: number | null, lang: Lang): string {
  return noches !== null && noches > 0 ? `${noches} ${lang === 'es' ? 'noches' : 'nights'}` : PALABRA.paquete[lang];
}

/**
 * Las palabras que rotan en el arranque de una sede, sacadas de su catálogo: una por tipo de
 * servicio (en el orden fijo de las tarjetas) y, por cada duración distinta de paquete con
 * estancia, «5 noches»; un paquete sin estancia entra como «Paquetes». Sin catálogo no hay palabras.
 */
export function palabrasDeSede(
  servicios: ServicioEtiquetable[] | null,
  paquetes: { noches: number | null }[] | null,
  lang: Lang,
): string[] {
  const tipos = new Set((servicios ?? []).map((s) => (s.tipo_servicio === 'bajo_demanda' ? 'paseo' : s.tipo_servicio)));
  const palabras = ORDEN_SEDE.filter((tipo) => tipo !== 'paquete' && tipos.has(tipo)).map((tipo) => palabraDeServicio(tipo, lang));
  const noches = [...new Set((paquetes ?? []).map((p) => p.noches).filter((n): n is number => n !== null && n > 0))].sort((a, b) => a - b);
  palabras.push(...noches.map((n) => palabraDePaquete(n, lang)));
  if ((paquetes ?? []).some((p) => !p.noches)) palabras.push(palabraDePaquete(null, lang));
  return palabras;
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
