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
// `mas`: las demás fotos de un paquete; la tarjeta las cambia como carrusel (la primera es `src`).
type Foto = FotoBase & { relleno?: true; mas?: FotoBase[] };

const FOTOS: Record<string, Foto> = {
  'servicio:sal-y-sol/pesca-deportiva': {
    src: '/catalogo/sal-y-sol-pesca-deportiva.webp',
    alt: {
      es: 'Jurel (cola amarilla) recién pescado frente a un acantilado',
      en: 'Freshly caught yellowtail by a sea cliff',
    },
  },
  'servicio:la-ventana-travel/avistamiento-ballenas-orcas': {
    src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
    alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' },
  },
  'servicio:la-ventana-travel/hospedaje-la-ventana': {
    src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
    alt: { es: 'Vista aérea del Hotel Casa Arrecife, con su terraza y el mar de La Ventana al fondo', en: 'Aerial view of Hotel Casa Arrecife, with its rooftop terrace and the La Ventana sea behind it' },
  },
  'servicio:la-ventana-travel/pesca-con-mosca': {
    src: '/catalogo/la-ventana-travel-pesca-con-mosca.webp',
    alt: { es: 'Un joven peleando un pez con la caña doblada, en alta mar', en: 'A young angler fighting a fish with a bent rod, out at sea' },
  },
  'servicio:transporte-la-paz/traslados-la-paz': {
    src: '/catalogo/transporte-la-paz-traslados-la-paz.webp',
    alt: { es: 'Una van blanca de DLS Tours y Transporte Turístico estacionada en una calle de La Paz', en: 'A white DLS Tours and Tourist Transport van parked on a street in La Paz' },
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
  },
  'paquete:paquete-5-noches': {
    src: '/catalogo/la-ventana-travel-paquete-5-noches.webp',
    alt: { es: 'Una persona nadando entre un enorme cardumen de rayas', en: 'A person swimming among a huge school of rays' },
    mas: [
      {
        src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
        alt: { es: 'Vista aérea del Hotel Casa Arrecife, con su terraza y el mar de La Ventana al fondo', en: 'Aerial view of Hotel Casa Arrecife, with its rooftop terrace and the La Ventana sea behind it' },
      },
      {
        src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
        alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' },
      },
    ],
  },
  'paquete:paquete-7-noches': {
    src: '/catalogo/la-ventana-travel-paquete-7-noches.webp',
    alt: { es: 'Una persona haciendo snorkel entre peces rayados', en: 'A person snorkeling among striped fish' },
    mas: [
      {
        src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
        alt: { es: 'Vista aérea del Hotel Casa Arrecife, con su terraza y el mar de La Ventana al fondo', en: 'Aerial view of Hotel Casa Arrecife, with its rooftop terrace and the La Ventana sea behind it' },
      },
      {
        src: '/catalogo/la-ventana-travel-hospedaje-fogata.webp',
        alt: { es: 'La fogata azul del patio del Hotel Casa Arrecife al atardecer', en: 'The blue fire pit in the Hotel Casa Arrecife courtyard at dusk' },
      },
    ],
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
