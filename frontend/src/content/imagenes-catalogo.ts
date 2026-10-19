// Fotos de las tarjetas del catálogo, hardcodeadas por ahora (decisión del dueño, 2026-10-16:
// prioridad lanzar). Sin campo en el backend ni R2: para pasar a la foto del admin se cambia
// solo `imagenDeCatalogo`; las tarjetas no se tocan. Cambiar una foto exige un deploy.
// Módulo puro (sin `server-only`): lo prueba el runner.
//
// Las fotos son WebP en `public/catalogo/`, de ≤ ~200 KB. Falta la de cada servicio y paquete
// de La Ventana, Puerto Chale y DLS (dependencia del dueño, Task 9.7).

type Lang = 'es' | 'en';
type Foto = { src: string; alt: Record<Lang, string> };

const FOTOS: Record<string, Foto> = {
  'servicio:sal-y-sol/pesca-deportiva': {
    src: '/catalogo/sal-y-sol-pesca-deportiva.webp',
    alt: {
      es: 'Jurel (cola amarilla) recién pescado frente a un acantilado',
      en: 'Freshly caught yellowtail by a sea cliff',
    },
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
