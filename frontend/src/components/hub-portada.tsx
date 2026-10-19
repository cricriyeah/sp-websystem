import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { hrefInicio } from '@/lib/routes';
import { ANCLA_HUB } from '@/lib/secciones-sede';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/**
 * Video y poster del héroe del hub. DE RELLENO (decisión del dueño, 2026-10-19: usar lo que ya
 * hay hasta subir lo real): son los de La Paz. El definitivo es neutro (varias sedes o Baja en
 * general), sin audio, ≤ 8 MB y ≥ 1280 px (Task 9.7). Con los dos en `null` la portada queda en
 * texto sobre arena con el mismo layout.
 */
const VIDEO_HUB: string | null = '/videos/videohero.webm';
const POSTER_HUB: string | null = '/photos/cola-amarilla-acantilado.webp';

type Props = {
  lang: Locale;
  textos: Pick<Dictionary['hubContenido'], 'titular' | 'subtexto' | 'ctaSedes'>;
};

/**
 * Héroe del hub: titular, una línea que es la de confianza y un solo CTA a las sedes. El alto lo
 * da el contenido (sin 100 dvh), para que en 360 × 740 las tarjetas de sede asomen.
 *
 * Server Component.
 */
export function HubPortada({ lang, textos }: Props) {
  const conMedio = Boolean(POSTER_HUB);
  const pila = (
    <div className="mx-auto w-full max-w-[1120px] px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
      {/* 36 px en móvil: «RESERVA EN BAJA / CON EMPRESAS / LOCALES» cabe en 3 renglones en 328 px
          con Consola Mono (0,586 em por carácter); desde 640 px, el tamaño display. */}
      <h1 className={cn('max-w-[18ch] texto-display text-[2.25rem] leading-[1.1] sm:text-[4rem] sm:leading-[1.05]', conMedio ? 'text-hero-ink' : 'text-foreground')}>{textos.titular}</h1>
      <p className={cn('mt-4 max-w-[52ch] text-lg leading-relaxed', conMedio ? 'text-hero-ink-soft' : 'text-tinta-suave')}>{textos.subtexto}</p>
      <Link href={hrefInicio(lang, ANCLA_HUB.sedes)} className={cn('mt-8', botonClases({ variante: 'principal' }))}>
        {textos.ctaSedes}
      </Link>
    </div>
  );

  return (
    <section className="pt-[var(--nav-alto)]">
      {conMedio ? (
        <HeroMedia imagen={POSTER_HUB} video={VIDEO_HUB} alt="" preload alto="contenido">
          {pila}
        </HeroMedia>
      ) : (
        <div className="flex max-h-[calc(100svh-var(--nav-alto)-120px)] flex-col justify-end bg-background">{pila}</div>
      )}
    </section>
  );
}
