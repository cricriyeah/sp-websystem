// frontend/src/lib/selector-experiencia.ts
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';

export type ChipExperiencia = {
  tipo: 'servicio' | 'paquete';
  slug: string;
  nombre: string;
  empresaSlug: string | null;
};

/**
 * Cruza `destacadas` (editorial, spec §4) contra el catálogo real de la sede.
 * El nombre del chip sale del catálogo, no del diccionario (que no lo
 * tiene). Una entrada sin contraparte en el catálogo (producto renombrado o
 * desactivado) se omite en silencio: menos chips, no una página rota.
 */
export function resolverChips(
  destacadas: SedeDestacada[],
  paquetes: PaqueteCatalogo[],
  servicios: ServicioCatalogo[],
): ChipExperiencia[] {
  const chips: ChipExperiencia[] = [];
  for (const d of destacadas) {
    if (d.tipo === 'servicio') {
      const match = servicios.find((s) =>
        s.slug === d.slug && (d.empresaSlug === undefined || s.empresa_slug === d.empresaSlug),
      );
      if (match) chips.push({ tipo: 'servicio', slug: match.slug, nombre: match.nombre, empresaSlug: match.empresa_slug });
    } else {
      const match = paquetes.find((p) => p.slug === d.slug);
      // Los paquetes destacados no llevan empresaSlug (spec §4, nota
      // "destacadas"): cual ruta de checkout usar depende de los
      // componentes del paquete, no de un lider unico.
      if (match) chips.push({ tipo: 'paquete', slug: match.slug, nombre: match.nombre, empresaSlug: null });
    }
  }
  return chips;
}

/**
 * Regla mecanica (spec §7): un chip abre inline el BookingBar heredado de
 * pesca SOLO si las tres condiciones se cumplen a la vez, sin importar lo
 * que diga `inlineable` en el diccionario de contenido.
 */
export function esInlineable(
  chip: ChipExperiencia,
  sedeSlug: string,
  empresaSlugPescaLegacy: string,
): boolean {
  return (
    sedeSlug === 'la-paz' &&
    chip.tipo === 'servicio' &&
    chip.slug === 'pesca-deportiva' &&
    chip.empresaSlug === empresaSlugPescaLegacy
  );
}
