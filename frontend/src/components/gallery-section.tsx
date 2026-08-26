import Image from 'next/image';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { MediaPlaceholder } from '@/components/media-placeholder';

type GallerySectionProps = {
  gallery: Dictionary['gallery'];
};

/**
 * Las 6 fotos son reales; el video sigue de placeholder porque todavia no
 * existe. El orden de `FOTOS` esta pareado con `gallery.photoHints` uno a uno
 * (el hint ahora es el `alt` de la foto real, no una toma pendiente) — si se
 * agrega o se quita una foto, hay que tocar los dos arreglos juntos.
 */
const FOTOS = [
  '/photos/pesca-del-dia-cubierta.png',
  '/photos/marlin-en-equipo.png',
  '/photos/grupo-cabrilla-costa.png',
  '/photos/pareja-dorados.png',
  '/photos/cana-doblada-dorado.png',
  '/photos/yellowtail-pelicanos-bahia.png',
];

/**
 * A sangre: sin contenedor, sin titulo. Las fotos hablan solas, el unico texto
 * es la nota chica de abajo, con el padding normal del sitio.
 */
export function GallerySection({ gallery }: GallerySectionProps) {
  return (
    <section id="galeria" className="scroll-mt-20 bg-background">
      <div className="grid grid-cols-2 gap-[3px] lg:grid-cols-4">
        <div className="col-span-2">
          <MediaPlaceholder
            hint={gallery.videoHint}
            aspect="fill"
            showHint={false}
            className="min-h-[240px] lg:min-h-[460px]"
          />
        </div>
        {gallery.photoHints.map((hint, i) => (
          <div key={hint} className="relative min-h-[240px] lg:min-h-[460px]">
            <Image
              src={FOTOS[i]}
              alt={hint}
              fill
              sizes="(min-width: 1024px) 25vw, 50vw"
              className="object-cover"
            />
          </div>
        ))}
      </div>

      <p className="px-6 pt-5 pb-16 text-sm text-muted sm:px-8 lg:px-12 lg:pb-20">
        {gallery.intro}
      </p>
    </section>
  );
}
