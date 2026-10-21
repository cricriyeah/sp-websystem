// Qué secciones lleva la página de una sede y en qué orden, sin React. Regla de F9: una
// sección sin contenido real no se pinta (nunca «pronto», nunca un sustituto). Solo importa
// tipos con `@/` (un import de valor con `@/` revienta en el runner) y no lee `empresas.ts`,
// que es `server-only`: la página le pasa los datos.
import { hayGaleria } from './etiquetas-catalogo';

export type SeccionId = 'hero' | 'reservar' | 'tranquilidad' | 'galeria' | 'temporadas' | 'opiniones' | 'preguntas';

export type Seccion = { id: SeccionId; estado?: 'normal' | 'vacio' | 'catalogo_caido' };

type Entrada = {
  /** `null` = el catálogo no respondió. */
  servicios: readonly unknown[] | null;
  paquetes: readonly unknown[] | null;
  resenas: readonly { confirmada: boolean }[];
  fotos: readonly { ancho: number; alto: number }[];
  faq: readonly unknown[];
  temporadas: readonly unknown[] | null | undefined;
};

function estadoDeReservar(servicios: Entrada['servicios'], paquetes: Entrada['paquetes']): Seccion['estado'] {
  if ((servicios?.length ?? 0) + (paquetes?.length ?? 0) > 0) return 'normal';
  return servicios === null || paquetes === null ? 'catalogo_caido' : 'vacio';
}

export function seccionesDeSede({ servicios, paquetes, resenas, fotos, faq, temporadas }: Entrada): Seccion[] {
  const secciones: Seccion[] = [
    { id: 'hero' },
    { id: 'reservar', estado: estadoDeReservar(servicios, paquetes) },
    // El pago, la cancelación y el clima van junto al producto: la política es real en las 4 empresas.
    { id: 'tranquilidad' },
  ];
  if (hayGaleria([...fotos])) secciones.push({ id: 'galeria' });
  if (temporadas && temporadas.length > 0) secciones.push({ id: 'temporadas' });
  if (resenas.some((r) => r.confirmada)) secciones.push({ id: 'opiniones' });
  if (faq.length > 0) secciones.push({ id: 'preguntas' });
  return secciones;
}

export const ANCLA_DE: Record<SeccionId, string> = {
  hero: 'inicio',
  reservar: 'reservar',
  tranquilidad: 'tranquilidad',
  galeria: 'galeria',
  temporadas: 'temporadas',
  opiniones: 'opiniones',
  preguntas: 'preguntas',
};

/** Los ids fijos del hub (`/[lang]`): cabecera, pie y página los toman de aquí. */
export const ANCLA_HUB = { mapa: 'mapa', sedes: 'sedes', comoFunciona: 'como-funciona', empresas: 'empresas' } as const;

/** Las bandas de la página de sede: blanco, gris y la banda negra de las cifras (F10). */
export type Fondo = 'blanco' | 'cafe-bruma' | 'tinta';

/**
 * El fondo que prefiere cada sección, en orden. La banda negra es solo de «tranquilidad» (las cifras).
 * El ritmo sale del cambio de tono entre bandas, sin rayas: nunca dos seguidas con el mismo.
 */
const PREFERENCIA: Record<Exclude<SeccionId, 'hero'>, readonly Fondo[]> = {
  reservar: ['blanco'],
  tranquilidad: ['tinta'],
  galeria: ['blanco', 'cafe-bruma'],
  temporadas: ['blanco', 'cafe-bruma'],
  opiniones: ['cafe-bruma', 'blanco'],
  preguntas: ['blanco', 'cafe-bruma'],
};

/**
 * Fondo de cada sección según su posición entre las que de verdad se pintan. El héroe es video a
 * sangre y no cuenta para la alternancia.
 */
export function fondosDeSecciones(ids: readonly SeccionId[]): Partial<Record<SeccionId, Fondo>> {
  const resultado: Partial<Record<SeccionId, Fondo>> = {};
  let anterior: Fondo | null = null;
  for (const id of ids) {
    if (id === 'hero') continue;
    const opciones: readonly Fondo[] = [...PREFERENCIA[id], 'blanco', 'cafe-bruma'];
    const fondo = opciones.find((f) => f !== anterior) ?? 'blanco';
    resultado[id] = fondo;
    anterior = fondo;
  }
  return resultado;
}

/** Fuera del menú: el héroe (es el inicio) y tranquilidad (va pegada a reservar). */
type SinEnlace = 'hero' | 'tranquilidad';
const SIN_ENLACE: readonly SeccionId[] = ['hero', 'tranquilidad'] satisfies SinEnlace[];
export type SeccionNavegable = Exclude<SeccionId, SinEnlace>;

/** Los enlaces del menú de la sede; la etiqueta sale de `dict.nav[claveNav]`. */
export function enlacesDeSede(ids: readonly SeccionId[]): { ancla: string; claveNav: SeccionNavegable }[] {
  return ids
    .filter((id): id is SeccionNavegable => !SIN_ENLACE.includes(id))
    .map((id) => ({ ancla: `#${ANCLA_DE[id]}`, claveNav: id }));
}
