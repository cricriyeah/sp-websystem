import type { SedeCuerpoContenido } from '@/content/sedes-tipos';
import { GaleriaMosaico } from '@/components/galeria-mosaico';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type GallerySectionProps = {
  id: string;
  titulo: string;
  /** Ya filtradas por la página: aptas (`fotosAptas`) y sin las que usan el héroe o las tarjetas. */
  fotos: NonNullable<SedeCuerpoContenido['galeria']>;
  /** Nombre de cada empresa de la galería, por slug. */
  empresas: Record<string, { nombre: string }>;
  textosVisor: { cerrar: string; anterior: string; siguiente: string; contador: string; pista: string };
  fondo: Fondo;
};

/**
 * Las fotos de los viajes en mosaico, con un visor a pantalla completa. Si la galería mezcla empresas, el
 * visor dice de cuál es cada foto; con una sola, no hace falta.
 *
 * Server Component (el mosaico y el visor son una isla cliente).
 */
export function GallerySection({ id, titulo, fotos, empresas, textosVisor, fondo }: GallerySectionProps) {
  const variasEmpresas = new Set(fotos.map((foto) => foto.empresaSlug)).size > 1;
  const vistas = fotos.map((foto) => ({
    src: foto.src,
    alt: foto.alt,
    ancho: foto.ancho,
    alto: foto.alto,
    leyenda: variasEmpresas ? empresas[foto.empresaSlug]?.nombre : undefined,
  }));

  return (
    <SectionShell id={id} fondo={fondo} titulo={titulo}>
      <GaleriaMosaico fotos={vistas} textosVisor={textosVisor} />
    </SectionShell>
  );
}
