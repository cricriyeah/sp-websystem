/**
 * Persistencia de la sede que el cliente eligió en el navbar.
 *
 * El `SedeSelector` del header vive en todas las páginas, pero solo el catálogo
 * lleva la sede en la URL (`?sede=`). En la portada y en el checkout no hay
 * parámetro, así que sin esto el selector se queda mostrando la primera sede de
 * la lista y aparenta estar congelado. Guardamos la elección en:
 *
 * - `localStorage`: lo lee el propio `SedeSelector` en el cliente.
 * - una cookie: la lee el catálogo (Server Component) en la primera carga, para
 *   no renderizar la sede equivocada antes de que hidrate el cliente.
 */
export const SEDE_STORAGE_KEY = 'psd_sede';

const TREINTA_DIAS = 60 * 60 * 24 * 30;

/** Escribe la sede elegida en localStorage y en la cookie. Nunca lanza. */
export function guardarSedePreferida(slug: string): void {
  if (!slug) return;
  try {
    window.localStorage.setItem(SEDE_STORAGE_KEY, slug);
  } catch {
    // Safari en privado / almacenamiento bloqueado: no es crítico.
  }
  try {
    document.cookie = `${SEDE_STORAGE_KEY}=${encodeURIComponent(slug)}; path=/; max-age=${TREINTA_DIAS}; samesite=lax`;
  } catch {
    // idem
  }
}

/** Lee la sede preferida en el cliente (localStorage y, si no, la cookie). */
export function leerSedePreferidaCliente(): string | undefined {
  try {
    const guardada = window.localStorage.getItem(SEDE_STORAGE_KEY);
    if (guardada) return guardada;
  } catch {
    // ignorar
  }
  try {
    const match = document.cookie.match(
      new RegExp(`(?:^|;\\s*)${SEDE_STORAGE_KEY}=([^;]+)`),
    );
    return match ? decodeURIComponent(match[1]) : undefined;
  } catch {
    return undefined;
  }
}
