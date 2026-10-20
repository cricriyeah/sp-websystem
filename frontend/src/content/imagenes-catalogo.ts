// Fotos de las tarjetas del catálogo, hardcodeadas por ahora (decisión del dueño, 2026-10-16:
// prioridad lanzar). Sin campo en el backend ni R2: para pasar a la foto del admin se cambia
// solo `imagenDeCatalogo`; las tarjetas no se tocan. Cambiar una foto exige un deploy.
// Módulo puro (sin `server-only`): lo prueba el runner.
//
// Las fotos son WebP en `public/catalogo/`, de ≤ ~200 KB. Falta la de cada servicio y paquete
// de La Ventana, Puerto Chale y DLS (dependencia del dueño, Task 9.7). Mientras llegan, esas
// claves llevan una foto que ya existe en el sitio marcada `relleno` (decisión del dueño,
// 2026-10-19): la tarjeta se ve completa y `test:fotos` sigue pidiendo la real.

type Lang = 'es' | 'en';
type Foto = { src: string; alt: Record<Lang, string>; relleno?: true };

const FOTOS: Record<string, Foto> = {
  'servicio:sal-y-sol/pesca-deportiva': {
    src: '/catalogo/sal-y-sol-pesca-deportiva.webp',
    alt: {
      es: 'Jurel (cola amarilla) recién pescado frente a un acantilado',
      en: 'Freshly caught yellowtail by a sea cliff',
    },
  },
  'servicio:la-ventana-travel/pesca-con-mosca': {
    src: '/photos/cana-doblada-dorado.webp',
    alt: { es: 'Caña doblada peleando un dorado', en: 'Rod bent, fighting a mahi' },
    relleno: true,
  },
  'servicio:la-ventana-travel/avistamiento-ballenas-orcas': {
    src: '/photos/yellowtail-pelicanos-bahia.webp',
    alt: { es: 'Panga en la bahía, con pelícanos alrededor', en: 'A panga in the bay, pelicans alongside' },
    relleno: true,
  },
  'servicio:la-ventana-travel/hospedaje-la-ventana': {
    src: '/ilustraciones/costa-placeholder.webp',
    alt: { es: 'Ilustración de la costa de Baja California Sur', en: 'Illustration of the Baja California Sur coast' },
    relleno: true,
  },
  'servicio:la-ventana-travel/traslado-aeropuerto-la-ventana': {
    src: '/ilustraciones/costa-placeholder.webp',
    alt: { es: 'Ilustración de la costa de Baja California Sur', en: 'Illustration of the Baja California Sur coast' },
    relleno: true,
  },
  'servicio:transporte-la-paz/traslados-la-paz': {
    src: '/ilustraciones/costa-placeholder.webp',
    alt: { es: 'Ilustración de la costa de Baja California Sur', en: 'Illustration of the Baja California Sur coast' },
    relleno: true,
  },
  'servicio:piratas-adventures/safari-marino': {
    src: '/photos/grupo-cabrilla-costa.webp',
    alt: { es: 'Grupo con su captura, cerca de la costa', en: 'A group with their catch, close to shore' },
    relleno: true,
  },
  'servicio:piratas-adventures/avistamiento-ballenas': {
    src: '/photos/yellowtail-pelicanos-bahia.webp',
    alt: { es: 'Panga en la bahía, con pelícanos alrededor', en: 'A panga in the bay, pelicans alongside' },
    relleno: true,
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
    src: '/photos/pesca-del-dia-cubierta.webp',
    alt: { es: 'La pesca del día completa en la cubierta', en: 'The full catch of the day on deck' },
    relleno: true,
  },
  'paquete:paquete-7-noches': {
    src: '/photos/pareja-dorados.webp',
    alt: { es: 'Dos amigos con su dorado', en: 'Two friends with their mahi' },
    relleno: true,
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

/**
 * «Todas o ninguna» por grupo: si a una tarjeta le falta la foto, ninguna del grupo la pinta
 * (la fila no queda dispareja). No se usa la foto de la empresa como sustituto.
 */
export function fotosDeGrupo(claves: string[]): boolean {
  return claves.length > 0 && claves.every((clave) => clave in FOTOS);
}
