import Image from 'next/image';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type GallerySectionProps = {
  gallery: Dictionary['gallery'];
};

/**
 * El orden de `FOTOS` esta pareado con `gallery.photoHints` uno a uno (el hint
 * es el `alt` de cada foto) — si se agrega o se quita una, hay que tocar los dos
 * arreglos juntos.
 *
 * La primera ocupa el doble de ancho y abre la reja. Ahi vivio un placeholder de
 * video que nunca se grabo; son 7 fotos justas para llenar dos filas completas
 * (1 doble + 2, y 4 abajo) sin dejar huecos.
 */
const FOTOS = [
  '/photos/dorado-bajo-toldo.webp',
  '/photos/pesca-del-dia-cubierta.webp',
  '/photos/marlin-en-equipo.webp',
  '/photos/grupo-cabrilla-costa.webp',
  '/photos/pareja-dorados.webp',
  '/photos/cana-doblada-dorado.webp',
  '/photos/yellowtail-pelicanos-bahia.webp',
];

/**
 * Titulo con el padding normal del sitio, y debajo la reja de fotos a sangre:
 * sin contenedor, para que las fotos ocupen todo el ancho disponible.
 */
export function GallerySection({ gallery }: GallerySectionProps) {
  return (
    <section id="galeria" className="scroll-mt-24 bg-background pt-24 lg:pt-32">
      <div className="mx-auto max-w-6xl px-6 pb-10 sm:px-8 lg:px-12 lg:pb-14">
        <span aria-hidden className="rev-regla mb-6 block h-[3px] w-12 bg-action" />
        <h2 className="max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]">
          {gallery.headline}
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-[3px] lg:grid-cols-4">
        {gallery.photoHints.map((hint, i) => (
          <div
            key={hint}
            className={`relative min-h-[240px] lg:min-h-[460px] ${i === 0 ? 'col-span-2' : ''}`}
          >
            <Image
              src={FOTOS[i]}
              alt={hint}
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
    </section>
  );
}
