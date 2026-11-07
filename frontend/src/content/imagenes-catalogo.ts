// Fotos de las tarjetas del catálogo, hardcodeadas por ahora (decisión del dueño, 2026-10-16:
// prioridad lanzar). Sin campo en el backend ni R2: para pasar a la foto del admin se cambia
// solo `imagenDeCatalogo`; las tarjetas no se tocan. Cambiar una foto exige un deploy.
// Módulo puro (sin `server-only`): lo prueba el runner.
//
// Las fotos son WebP en `public/catalogo/`, de ≤ ~200 KB. Falta la de cada servicio y paquete
// de La Ventana, Puerto Chale y DLS (dependencia del dueño, Task 9.7). Mientras llegan, esas
// claves llevan una foto que ya existe en el sitio marcada `relleno` (decisión del dueño,
// 2026-10-19): la tarjeta se ve completa y `test:fotos` sigue pidiendo la real.
//
// El relleno no puede contradecir el servicio: ballenas, safari, pesca con mosca, hospedaje y
// traslados van SIN foto hasta tener la suya (antes mostraban pesca de altura o una ilustración
// rotulada «Destino Los Cabos»): su tarjeta es un bloque del color de su tipo con su palabra.

type Lang = 'es' | 'en';
type FotoBase = { src: string; alt: Record<Lang, string> };
// `ancho` y `alto`: los de la imagen, que pide el visor de la galería.
type FotoGaleria = FotoBase & { ancho: number; alto: number };
// `mas`: las demás fotos de un paquete; la tarjeta las cambia como carrusel (la primera es `src`).
// `galeria`: todas las fotos que se ven en el detalle, con el visor a pantalla completa; es una lista aparte
// para que la tarjeta no rote entre seis fotos.
type Foto = FotoBase & { relleno?: true; mas?: FotoBase[]; galeria?: FotoGaleria[] };

// Fotos del hospedaje de La Ventana (de ejemplo, sin pie de foto). Se comparten entre la tarjeta y la galería.
const HOSPEDAJE_VISTA_AEREA: FotoGaleria = {
  src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp', ancho: 2750, alto: 1536,
  alt: { es: 'Vista aérea del hospedaje, con su terraza y el mar al fondo', en: 'Aerial view of the lodging, with its terrace and the sea behind it' },
};
const HOSPEDAJE_HABITACION_NICHOS: FotoGaleria = {
  src: '/catalogo/la-ventana-travel-hospedaje-habitacion-nichos.webp', ancho: 1537, alto: 1023,
  alt: { es: 'Habitación con cama azul y nichos iluminados en la pared', en: 'Bedroom with a blue bed and lit niches in the wall' },
};
const HOSPEDAJE_HABITACION_NAUTICA: FotoGaleria = {
  src: '/catalogo/la-ventana-travel-hospedaje-habitacion-nautica.webp', ancho: 1448, alto: 1086,
  alt: { es: 'Habitación con la cama sobre cajones de madera y detalles marinos', en: 'Bedroom with the bed over wooden drawers and nautical details' },
};
const HOSPEDAJE_ESTUDIO_VISTA_MAR: FotoGaleria = {
  src: '/catalogo/la-ventana-travel-hospedaje-estudio-vista-mar.webp', ancho: 1537, alto: 1023,
  alt: { es: 'Estudio con puerta corrediza y vista al mar', en: 'Studio with a sliding door and a view of the sea' },
};
const HOSPEDAJE_COCINA: FotoGaleria = {
  src: '/catalogo/la-ventana-travel-hospedaje-cocina.webp', ancho: 2400, alto: 1792,
  alt: { es: 'Cocina compartida con barra de mármol', en: 'Shared kitchen with a marble counter' },
};
const HOSPEDAJE_FOGATA: FotoGaleria = {
  src: '/catalogo/la-ventana-travel-hospedaje-fogata.webp', ancho: 1856, alto: 2304,
  alt: { es: 'Patio con una fogata azul al atardecer', en: 'Courtyard with a blue fire pit at dusk' },
};
const ORCAS: FotoBase = {
  src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
  alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' },
};
const SNORKEL: FotoBase = {
  src: '/catalogo/la-ventana-travel-paquete-7-noches.webp',
  alt: { es: 'Una persona haciendo snorkel entre peces rayados', en: 'A person snorkeling among striped fish' },
};
const RAYAS: FotoBase = {
  src: '/catalogo/la-ventana-travel-paquete-5-noches.webp',
  alt: { es: 'Una persona nadando entre un enorme cardumen de rayas', en: 'A person swimming among a huge school of rays' },
};
// El orden de la galería: primero el lugar, luego dónde se duerme, al final las áreas comunes.
const GALERIA_HOSPEDAJE: FotoGaleria[] = [
  HOSPEDAJE_VISTA_AEREA, HOSPEDAJE_HABITACION_NICHOS, HOSPEDAJE_HABITACION_NAUTICA,
  HOSPEDAJE_ESTUDIO_VISTA_MAR, HOSPEDAJE_COCINA, HOSPEDAJE_FOGATA,
];

// Fotos reales de La Paz que también rotan en las tarjetas y el héroe del detalle (dueño, 2026-11-07: carrusel
// automático de 4 fotos, y solo fotos que ya están en la galería de la sede).
const LA_PAZ_JUREL_PELICANOS: FotoBase = {
  src: '/photos/yellowtail-pelicanos-bahia.webp',
  alt: { es: 'De regreso a la bahía, con pelícanos alrededor', en: 'Back in the bay, with pelicans all around' },
};
const LA_PAZ_DORADO_BAJO_TOLDO: FotoBase = {
  src: '/photos/dorado-bajo-toldo.webp',
  alt: { es: 'Dorado recién subido, a la sombra del toldo', en: 'Mahi just brought aboard, in the shade of the canopy' },
};
const LA_PAZ_CLIENTES_TUNA: FotoBase = {
  src: '/photos/clientes-tuna.webp',
  alt: { es: 'Dos pescadores sonríen con un pez grande recién subido a la panga', en: 'Two anglers smile with a big fish just brought aboard the panga' },
};
const PESCA_SAL_Y_SOL: FotoBase = {
  src: '/catalogo/sal-y-sol-pesca-deportiva.webp',
  alt: { es: 'Jurel (cola amarilla) recién pescado frente a un acantilado', en: 'Freshly caught yellowtail by a sea cliff' },
};
const VAN_DLS: FotoBase = {
  src: '/catalogo/transporte-la-paz-traslados-la-paz.webp',
  alt: { es: 'Una van blanca de DLS Tours y Transporte Turístico estacionada en una calle de La Paz', en: 'A white DLS Tours and Tourist Transport van parked on a street in La Paz' },
};
const BALANDRA: FotoBase = {
  src: '/catalogo/transporte-la-paz-balandra.webp',
  alt: { es: 'Una van blanca de DLS estacionada junto al letrero de colores de Balandra, con los cerros detrás', en: 'A white DLS van parked next to the colorful Balandra sign, with the hills behind it' },
};

const FOTOS: Record<string, Foto> = {
  'servicio:sal-y-sol/pesca-deportiva': {
    ...PESCA_SAL_Y_SOL,
    // La principal y tres de la galería de La Paz; ni joel-dorado ni cliente-dorado (el dueño no las quiere aquí, 2026-11-07).
    mas: [LA_PAZ_CLIENTES_TUNA, LA_PAZ_JUREL_PELICANOS, LA_PAZ_DORADO_BAJO_TOLDO],
  },
  'servicio:la-ventana-travel/avistamiento-ballenas-orcas': {
    src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
    alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' },
  },
  'servicio:la-ventana-travel/hospedaje-la-ventana': {
    src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
    alt: { es: 'Vista aérea del Hotel Casa Arrecife, con su terraza y el mar de La Ventana al fondo', en: 'Aerial view of Hotel Casa Arrecife, with its rooftop terrace and the La Ventana sea behind it' },
    mas: [HOSPEDAJE_HABITACION_NICHOS, HOSPEDAJE_ESTUDIO_VISTA_MAR, HOSPEDAJE_FOGATA],
  },
  'servicio:la-ventana-travel/pesca-con-mosca': {
    src: '/catalogo/la-ventana-travel-pesca-con-mosca.webp',
    alt: { es: 'Un joven peleando un pez con la caña doblada, en alta mar', en: 'A young angler fighting a fish with a bent rod, out at sea' },
  },
  'servicio:transporte-la-paz/traslados-la-paz': {
    ...VAN_DLS,
    mas: [BALANDRA],
  },
  'servicio:piratas-adventures/pesca-deportiva': {
    src: '/photos/dorado-bajo-toldo.webp',
    alt: { es: 'Dorado recién subido, a la sombra del toldo', en: 'Mahi just brought aboard, in the shade of the canopy' },
    relleno: true,
  },
  'paquete:pesca-traslado': {
    src: '/photos/marlin-en-equipo.webp',
    alt: { es: 'Marlin capturado en equipo, listo para la foto y la liberación', en: 'A marlin caught as a team, ready for the photo and release' },
    relleno: true,
    // Sin cliente-dorado (dueño, 2026-11-07).
    mas: [LA_PAZ_DORADO_BAJO_TOLDO, VAN_DLS],
  },
  'paquete:paquete-5-noches': {
    ...RAYAS,
    // El snorkel en lugar de la vista aérea de la casa (dueño, 2026-11-07).
    mas: [HOSPEDAJE_HABITACION_NICHOS, SNORKEL, ORCAS],
    galeria: GALERIA_HOSPEDAJE,
  },
  'paquete:paquete-7-noches': {
    ...SNORKEL,
    // Las rayas en lugar de la vista aérea de la casa (dueño, 2026-11-07).
    mas: [HOSPEDAJE_HABITACION_NAUTICA, HOSPEDAJE_FOGATA, RAYAS],
    galeria: GALERIA_HOSPEDAJE,
  },
};

export const claveDeServicio = (empresaSlug: string, slug: string) => `servicio:${empresaSlug}/${slug}`;
export const claveDePaquete = (slug: string) => `paquete:${slug}`;

export function imagenDeCatalogo(clave: string, lang: Lang): { src: string; alt: string } | null {
  const foto = FOTOS[clave];
  if (!foto) {
    if (process.env.NODE_ENV === 'development') console.warn(`[catalogo] sin foto para ${clave}`);
    return null;
  }
  return { src: foto.src, alt: foto.alt[lang] };
}

/** Todas las fotos de un producto (la principal y las demás), en su orden; vacío si no tiene. */
export function imagenesDeCatalogo(clave: string, lang: Lang): { src: string; alt: string }[] {
  const foto = FOTOS[clave];
  if (!foto) return [];
  return [foto, ...(foto.mas ?? [])].map((f) => ({ src: f.src, alt: f.alt[lang] }));
}

/** Las fotos de la galería del detalle de un producto; vacío si no tiene galería. */
export function galeriaDeCatalogo(clave: string, lang: Lang): { src: string; alt: string; ancho: number; alto: number }[] {
  return (FOTOS[clave]?.galeria ?? []).map((f) => ({ src: f.src, alt: f.alt[lang], ancho: f.ancho, alto: f.alto }));
}
