// frontend/src/lib/reconciliar-sedes.ts
import type { SedeIndiceEntry } from '@/content/sedes-tipos';

/**
 * Intersección índice × API (spec §4, "regla de reconciliación"). Pura: no
 * hace fetch, recibe `sedesApi` ya resuelto por el caller (`getSedes()`
 * consumido afuera). `sedesApi === null` significa que `getSedes()` falló
 * (rechazo de red O timeout — ver Step 4 más abajo): se falla abierto y se
 * devuelven todas las sedes del índice sin filtrar, nunca una lista vacía
 * por un error de red. Opera solo sobre `SedeIndiceEntry` (client-safe) — el
 * contenido largo por sede vive en `content/sedes-cuerpo.ts` (server-only) y
 * nunca pasa por esta función.
 */
export function sedesActivas(
  indice: Record<string, SedeIndiceEntry>,
  sedesApi: { slug: string }[] | null,
): SedeIndiceEntry[] {
  const slugs = Object.keys(indice);
  const slugsAMostrar =
    sedesApi === null ? slugs : slugs.filter((slug) => sedesApi.some((s) => s.slug === slug));

  return slugsAMostrar.map((slug) => indice[slug]);
}
