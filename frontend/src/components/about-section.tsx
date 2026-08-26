import Image from 'next/image';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type AboutSectionProps = {
  about: Dictionary['about'];
};

/**
 * La foto rompe hasta el borde: va a sangre en su columna, sin el contenedor
 * `max-w-6xl` que usa el texto. Los datos del viaje (duracion, hora, cupo, ano)
 * ya viven en la portada — repetirlos aqui era la misma tabla dos veces.
 */
export function AboutSection({ about }: AboutSectionProps) {
  return (
    <section id="nosotros" className="scroll-mt-20 grid bg-surface lg:grid-cols-2">
      <div className="relative min-h-[320px] lg:min-h-[620px]">
        <Image
          src="/photos/capitan-cabrilla-bahia.png"
          alt={about.photoHint}
          fill
          sizes="(min-width: 1024px) 50vw, 100vw"
          className="object-cover"
        />
      </div>

      <div className="flex flex-col justify-center gap-6 px-6 py-16 sm:px-8 lg:px-20 lg:py-24">
        <span aria-hidden className="rev-regla block h-[3px] w-12 bg-action" />
        <h2 className="max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[50px]">
          {about.headline}
        </h2>
        <p className="max-w-[52ch] text-lg leading-relaxed text-foreground">{about.body1}</p>
        <p className="max-w-[52ch] text-lg leading-relaxed text-muted">{about.body2}</p>
      </div>
    </section>
  );
}
