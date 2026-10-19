import type { SedeCuerpoContenido } from '@/content/sedes-tipos';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { FotoFundido } from '@/components/ui/foto-fundido';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type GallerySectionProps = {
  id: string;
  titulo: string;
  /** Ya filtradas por la página: aptas (`fotosAptas`) y sin las que usan el héroe o las tarjetas. */
  fotos: NonNullable<SedeCuerpoContenido['galeria']>;
  /** Nombre y logo de cada empresa de la galería, por slug. */
  empresas: Record<string, { nombre: string; logo?: string }>;
  fondo: Fondo;
  borde: boolean;
};

/**
 * Las fotos de los viajes, cada una en su proporción real: columnas (2 hasta 1024 px, 3 desde
 * ahí) dentro del contenido, sin recortes ni lightbox. Si la galería mezcla empresas, cada foto
 * lleva debajo, nunca encima, el sello y el nombre de la suya.
 *
 * Server Component (el fundido de entrada es de `FotoFundido`).
 */
export function GallerySection({ id, titulo, fotos, empresas, fondo, borde }: GallerySectionProps) {
  const variasEmpresas = new Set(fotos.map((foto) => foto.empresaSlug)).size > 1;

  return (
    <SectionShell id={id} fondo={fondo} borde={borde} titulo={titulo}>
      <div className="mt-10 columns-2 gap-3 lg:columns-3">
        {fotos.map((foto, i) => {
          const empresa = empresas[foto.empresaSlug];
          return (
            <figure key={foto.src} className="mb-3 break-inside-avoid">
              <FotoFundido
                src={foto.src}
                alt={foto.alt}
                width={foto.ancho}
                height={foto.alto}
                loading={i < 2 ? 'eager' : 'lazy'}
                sizes="(min-width: 1120px) 365px, (min-width: 1024px) 33vw, 50vw"
                className="h-auto w-full rounded-card"
              />
              {variasEmpresas && empresa && (
                <figcaption className="mt-2 flex items-center gap-2 texto-pequeno text-muted">
                  <span aria-hidden="true" className="inline-flex">
                    <EmpresaSello nombre={empresa.nombre} logo={empresa.logo} tamano={24} />
                  </span>
                  {empresa.nombre}
                </figcaption>
              )}
            </figure>
          );
        })}
      </div>
    </SectionShell>
  );
}
