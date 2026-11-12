/**
 * Reseñas del perfil de Google de Sun Baja Experience (la marca, no una empresa).
 *
 * Dueño, 2026-11-11: hay 5 en Google; van las 5 en tarjetas que se arrastran, con su nombre y sin cifra grande (ni
 * promedio ni estrellas). Mientras el dueño no pase el texto real, van 5 de RELLENO que se notan como tales: sin nombre
 * inventado ni opinión inventada, para que nadie las lea como reseñas de verdad. Al pegar las reales, `relleno`
 * se quita.
 */
import { REDES_MARCA } from './redes-marca';

export type ResenaMarca = {
  autor: string;
  texto: string;
  idioma: 'es' | 'en';
  /** Las estrellas que puso ese cliente en Google (1 a 5), tal cual. RELLENO: 5 hasta pegar las reales. */
  estrellas: 1 | 2 | 3 | 4 | 5;
  /** Sedes donde se muestra: la del servicio que reseñó el cliente. */
  sedes: readonly string[];
  /** Texto de ejemplo, pendiente de la reseña real. */
  relleno?: true;
};

const PERFIL_GOOGLE = REDES_MARCA.find((r) => r.nombre === 'Google')?.url ?? '';

export const FUENTE_GOOGLE = { nombre: 'Google', url: PERFIL_GOOGLE };

export const RESENAS_MARCA: readonly ResenaMarca[] = [
  {
    autor: 'Cliente 1 (nombre como aparece en Google)',
    texto: 'Aquí va el texto de la primera reseña de Google, copiado tal cual lo escribió el cliente.',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
    relleno: true,
  },
  {
    autor: 'Cliente 2 (nombre como aparece en Google)',
    texto: 'Aquí va el texto de la segunda reseña de Google.',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
    relleno: true,
  },
  {
    autor: 'Cliente 3 (nombre como aparece en Google)',
    texto: 'Aquí va el texto de la tercera reseña de Google.',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
    relleno: true,
  },
  {
    autor: 'Cliente 4 (nombre como aparece en Google)',
    texto: 'Aquí va el texto de la cuarta reseña de Google.',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
    relleno: true,
  },
  {
    autor: 'Cliente 5 (nombre como aparece en Google)',
    texto: 'Aquí va el texto de la quinta reseña de Google.',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
    relleno: true,
  },
];

/** Las reseñas de la marca que van en una sede, en el orden de la lista. */
export function resenasMarcaDeSede(sedeSlug: string): readonly ResenaMarca[] {
  return RESENAS_MARCA.filter((r) => r.sedes.includes(sedeSlug));
}
