import Image from 'next/image';
import type { SedeCuerpoContenido } from '@/content/sedes-tipos';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type GallerySectionProps = {
  id: string;
  titulo: string;
  /** Las fotos salen del cuerpo de la sede; el `alt` de cada una viaja con ella. */
  fotos: NonNullable<SedeCuerpoContenido['galeria']>;
  fondo: Fondo;
  borde: boolean;
};

/**
 * La primera ocupa el doble de ancho y abre la reja. Ahi vivio un placeholder de
 * video que nunca se grabo; son 7 fotos justas para llenar dos filas completas
 * (1 doble + 2, y 4 abajo) sin dejar huecos.
 */
/**
 * Titulo con el padding normal del sitio, y debajo la reja de fotos a sangre:
 * sin contenedor, para que las fotos ocupen todo el ancho disponible.
 */
export function GallerySection({ id, titulo, fotos, fondo, borde }: GallerySectionProps) {
  return (
    <SectionShell id={id} fondo={fondo} borde={borde} titulo={titulo} aSangre>
      <div className="grid grid-cols-2 gap-[3px] lg:grid-cols-4">
        {fotos.map((foto, i) => (
          <div
            key={foto.src}
            className={`relative min-h-[240px] lg:min-h-[460px] ${i === 0 ? 'col-span-2' : ''}`}
          >
            <Image
              src={foto.src}
              alt={foto.alt}
              fill
              sizes={
                i === 0
                  ? '(min-width: 1024px) 50vw, 100vw'
                  : '(min-width: 1024px) 25vw, 50vw'
              }
              className="object-cover"
            />
          </div>
        ))}
      </div>
    </SectionShell>
  );
}
