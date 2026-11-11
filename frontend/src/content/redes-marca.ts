/**
 * Perfiles de Sun Baja Experience (la marca, no las empresas), confirmados por el dueño el 2026-11-11.
 * Cada empresa tiene los suyos en `empresas.ts`.
 */
export type RedMarca = { nombre: 'Instagram' | 'TikTok' | 'Facebook' | 'Google'; url: string };

export const REDES_MARCA: readonly RedMarca[] = [
  { nombre: 'Instagram', url: 'https://www.instagram.com/sunbajaexperiences' },
  { nombre: 'TikTok', url: 'https://www.tiktok.com/@sunbajaexperiences' },
  { nombre: 'Facebook', url: 'https://www.facebook.com/sunbajaexperiences/' },
  // Enlace para compartir del perfil de Google Maps: redirige al perfil, sirve para el visitante.
  { nombre: 'Google', url: 'https://share.google/W9a3EUEzPReQN1Jwp' },
];

/**
 * Lo que va en `sameAs` del JSON-LD: solo URLs canónicas de perfil. El enlace corto de Google es una
 * redirección, no la dirección del perfil, y Google no lo usaría para unir la marca.
 */
export const SAME_AS_MARCA: readonly string[] = REDES_MARCA.filter((r) => r.nombre !== 'Google').map((r) => r.url);
