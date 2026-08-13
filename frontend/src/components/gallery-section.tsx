import type { Dictionary } from '@/app/[lang]/dictionaries';
import { MediaPlaceholder } from '@/components/media-placeholder';

type GallerySectionProps = {
  gallery: Dictionary['gallery'];
};

/**
 * Galeria del viaje. En pesca deportiva la prueba mas fuerte son las fotos, asi
 * que la estructura queda lista y cada hueco dice que toma le falta.
 */
export function GallerySection({ gallery }: GallerySectionProps) {
  return (
    <section id="galeria" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {gallery.headline}
        </h2>
        <p className="mt-5 max-w-[60ch] text-base leading-relaxed text-muted">{gallery.intro}</p>

        <div className="mt-12 grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <MediaPlaceholder hint={gallery.videoHint} aspect="video" kind="video" />
          </div>
          <MediaPlaceholder hint={gallery.photoHints[0]} aspect="video" />
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {gallery.photoHints.slice(1).map((hint) => (
            <MediaPlaceholder key={hint} hint={hint} aspect="square" />
          ))}
        </div>

        <p className="mt-10 max-w-[60ch] text-sm leading-relaxed text-muted">{gallery.note}</p>
      </div>
    </section>
  );
}
