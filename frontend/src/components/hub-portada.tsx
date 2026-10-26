import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { hrefInicio } from '@/lib/routes';
import { ANCLA_HUB } from '@/lib/secciones-sede';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';

/**
 * Video y poster del héroe del hub. DE RELLENO (decisión del dueño, 2026-10-19: usar lo que ya
 * hay hasta subir lo real): son los de La Paz. El definitivo es neutro (varias sedes o Baja en
 * general), sin audio, ≤ 8 MB y ≥ 1280 px (Task 9.7).
 */
const VIDEO_HUB = '/videos/nuevo-hero.webm';
const POSTER_HUB = '/photos/cola-amarilla-acantilado.webp';

type Props = {
  lang: Locale;
  textos: Pick<Dictionary['hubContenido'], 'titularLineas' | 'titularSecundario' | 'subtexto' | 'ctaSedes'>;
};

/**
 * Arranque de campaña (F10): el video del mar a pantalla completa, el titular gigante en blanco
 * (una línea por renglón: `texto-gigante` no se parte), una frase y un solo CTA a las sedes.
 *
 * Server Component.
 */
export function HubPortada({ lang, textos }: Props) {
  return (
    <section>
      <HeroMedia imagen={POSTER_HUB} video={VIDEO_HUB} alt="" preload alto="completo">
        <div className="mx-auto w-full max-w-[1440px] px-4 pb-10 pt-[calc(var(--nav-alto)+1.5rem)] sm:px-6 sm:pb-14 lg:px-12">
          <h1 className="texto-gigante text-hero-ink">
            {textos.titularLineas.map((linea) => (
              <span key={linea} className="block">{linea}</span>
            ))}
            {/* Lo que se ofrece y dónde, en el mismo titular: «Mar adentro» sigue gigante y esta línea, más chica,
                lo dice con palabras (la letra gigante no cabría en el teléfono). */}
            <span className="mt-3 block texto-seccion">{textos.titularSecundario}</span>
          </h1>
          <div className="mt-6 flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
            <p className="max-w-[44ch] text-xl leading-snug text-hero-ink">{textos.subtexto}</p>
            <Link href={hrefInicio(lang, ANCLA_HUB.sedes)} className={botonClases({ variante: 'campana-claro' })}>
              {textos.ctaSedes}
            </Link>
          </div>
        </div>
      </HeroMedia>
    </section>
  );
}
