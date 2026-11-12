/**
 * Reseñas del perfil de Google de Sun Baja Experience (la marca, no una empresa).
 *
 * Dueño, 2026-11-11: van las de Google en tarjetas que se arrastran, con su nombre y sin cifra grande (ni promedio
 * ni estrellas sumadas). Las 5 reales las pasó el dueño el 2026-11-12 (capturas de Google Maps): nombre, estrellas y
 * texto tal cual, con sus faltas, en el idioma en que se escribieron. Primero las más largas y concretas.
 *
 * `traduccion` es el texto en el otro idioma (es ↔ en), hecho por nosotros: la página en ese idioma lo enseña, dice
 * que es una traducción y deja ver el original (dueño, 2026-11-12).
 */
import { PERFIL_GOOGLE_MARCA } from './redes-marca';

export type ResenaMarca = {
  autor: string;
  texto: string;
  idioma: 'es' | 'en';
  /** El texto en el otro idioma del sitio (si `idioma` es `es`, en inglés, y al revés). */
  traduccion: string;
  /** Las estrellas que puso ese cliente en Google (1 a 5), tal cual. */
  estrellas: 1 | 2 | 3 | 4 | 5;
  /** Sedes donde se muestra: la del servicio que reseñó el cliente. */
  sedes: readonly string[];
};

const PERFIL_GOOGLE = PERFIL_GOOGLE_MARCA;

export const FUENTE_GOOGLE = { nombre: 'Google', url: PERFIL_GOOGLE };

export const RESENAS_MARCA: readonly ResenaMarca[] = [
  {
    autor: 'Sebastian Gorostieta Olivas',
    texto:
      'Vivi mil experiencias inolvidables cuando vine a la paz gracias a la atencion y servicios que ofrecen, cuando vuelva a venir seguro reservo con ustedes de nuevo!!',
    traduccion:
      'I had a thousand unforgettable experiences when I came to La Paz, thanks to the service and the tours you offer. When I come back I will definitely book with you again!!',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
  },
  {
    autor: 'Gustavo Santaolalla',
    texto: 'Had a big time with this guys haha! Excellent English support and super professionals.',
    traduccion: '¡La pasamos en grande con ellos, jaja! Excelente atención en inglés y súper profesionales.',
    idioma: 'en',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
  },
  {
    autor: 'araceli fernandez',
    texto: 'Me encantó el trato amable y profesional de todo el personal a cargo y la atención al cliente!',
    traduccion: 'I loved the friendly, professional treatment from all the staff in charge, and the customer service!',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
  },
  {
    autor: 'Lalo Srz',
    texto: 'Personal amable, buena organización y una experiencia inolvidable.',
    traduccion: 'Friendly staff, good organization and an unforgettable experience.',
    idioma: 'es',
    estrellas: 4,
    sedes: ['la-paz', 'la-ventana'],
  },
  {
    autor: 'Lara Juárez Carlos Abel #13',
    texto: 'Super bueno, 100% recomendado',
    traduccion: 'Super good, 100% recommended',
    idioma: 'es',
    estrellas: 5,
    sedes: ['la-paz', 'la-ventana'],
  },
];

/** Las reseñas de la marca que van en una sede, en el orden de la lista. */
export function resenasMarcaDeSede(sedeSlug: string): readonly ResenaMarca[] {
  return RESENAS_MARCA.filter((r) => r.sedes.includes(sedeSlug));
}
