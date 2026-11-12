/**
 * Perfiles de Sun Baja Experience (la marca, no las empresas), confirmados por el dueño el 2026-11-11.
 * Cada empresa tiene los suyos en `empresas.ts`.
 */
export type RedMarca = { nombre: 'Instagram' | 'TikTok' | 'Facebook'; url: string };

/** Los iconos de «Síguenos» del pie. Google salió de ahí (dueño, 2026-11-12); su perfil sigue en las reseñas. */
export const REDES_MARCA: readonly RedMarca[] = [
  { nombre: 'Instagram', url: 'https://www.instagram.com/sunbajaexperiences' },
  { nombre: 'TikTok', url: 'https://www.tiktok.com/@sunbajaexperiences' },
  { nombre: 'Facebook', url: 'https://www.facebook.com/sunbajaexperiences/' },
];

/** Enlace para compartir del perfil de Google Maps: redirige al perfil. Lo usan las reseñas («Ver en Google»). */
export const PERFIL_GOOGLE_MARCA = 'https://share.google/W9a3EUEzPReQN1Jwp';

/** Ficha de Sun Baja Experiences en TripAdvisor: la insignia del pie enlaza aquí. */
export const PERFIL_TRIPADVISOR_MARCA =
  'https://www.tripadvisor.com.mx/Attraction_Review-g150771-d34807297-Reviews-Sun_Baja_Experiences-La_Paz_Baja_California.html';

/**
 * Lo que va en `sameAs` del JSON-LD: solo URLs canónicas de perfil. El enlace corto de Google es una
 * redirección, no la dirección del perfil, y Google no lo usaría para unir la marca.
 */
export const SAME_AS_MARCA: readonly string[] = [...REDES_MARCA.map((r) => r.url), PERFIL_TRIPADVISOR_MARCA];
