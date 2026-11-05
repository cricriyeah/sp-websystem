import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { hrefInicio } from '@/lib/routes';
import { ANCLA_HUB } from '@/lib/secciones-sede';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';

/**
 * Foto del héroe del hub. Desde 2026-11-04 (pedido del dueño) va la foto de la panga rumbo a la
 * pesca en lugar del video: sin video, la foto es el LCP y se precarga.
 */
const FOTO_HUB = '/photos/panga-rumbo-a-la-pesca.webp';

type Props = {
  lang: Locale;
  textos: Pick<Dictionary['hubContenido'], 'titularLineas' | 'titularSecundario' | 'subtexto' | 'ctaSedes'>;
};

/**
 * Arranque de campaña (F10): la foto de la panga a pantalla completa, el titular gigante en blanco
 * (una línea por renglón: `texto-gigante` no se parte), una frase y un solo CTA a las sedes.
 *
 * Server Component.
 */
export function HubPortada({ lang, textos }: Props) {
  return (
    <section>
      <HeroMedia imagen={FOTO_HUB} video={null} alt="" preload alto="completo">
        <div className="mx-auto w-full max-w-[1440px] px-pagina pb-10 pt-[calc(var(--nav-alto)+1.5rem)] sm:pb-14">
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
