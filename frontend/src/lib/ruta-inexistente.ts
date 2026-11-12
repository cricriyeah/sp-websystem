/**
 * ¿Una URL de sede o de servicio que no puede existir? (Search Console, 2026-11-11.)
 *
 * Las páginas de sede y de servicio tienen `loading.tsx`: la respuesta empieza a salir (200) antes de que la página
 * sepa si el slug existe, y un `notFound()` adentro deja un «soft 404» (200 con `noindex`). Con las listas fijas de
 * sedes y empresas el proxy lo sabe antes, sin pedir nada al catálogo, y manda la URL a la ruta comodín, que responde
 * 404 de verdad. Un servicio desconocido de una empresa que sí existe sigue siendo soft 404: saberlo pide el catálogo.
 *
 * Puro, sin Next: lo usa `proxy.ts` y lo prueba `tests/ruta-inexistente.test.cjs`.
 */
import { SEDES_INDICE } from '../content/sedes-indice';
import { MARCAS } from '../content/empresas-marca';

const SEDE = /^\/(?:es|en)\/sede\/([^/]+)/;
const SERVICIO = /^\/(?:es|en)\/servicio\/([^/]+)/;

export function rutaInexistente(pathname: string): boolean {
  const sede = SEDE.exec(pathname)?.[1];
  if (sede !== undefined) return !Object.hasOwn(SEDES_INDICE, decodeURIComponent(sede));
  const empresa = SERVICIO.exec(pathname)?.[1];
  if (empresa !== undefined) return !MARCAS.some((marca) => marca.slug === decodeURIComponent(empresa));
  return false;
}
