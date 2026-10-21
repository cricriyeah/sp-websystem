import Link from 'next/link';
import type { SedeHeroContenido } from '@/content/sedes-tipos';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { PalabraRota } from '@/components/palabra-rota';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';

type SedeHeroProps = {
  nombre: string;
  contenido: SedeHeroContenido;
  /** Lo que vende la sede, sacado de su catálogo (`palabrasDeSede`); vacío si el catálogo no respondió. */
  palabras: string[];
  textos: { cta: string };
};

/**
 * Arranque de campaña de una sede (F10): el video del mar a pantalla completa, una palabra gigante
 * arriba que cambia con lo que se reserva ahí, el nombre de la sede como `h1`, una frase y un solo
 * botón que baja a lo que se puede reservar. Lo comparten las tres sedes.
 *
 * Server Component (la palabra que rota es una isla cliente).
 */
export function SedeHero({ nombre, contenido, palabras, textos }: SedeHeroProps) {
  return (
    <section className="pt-[var(--nav-alto)]">
      <HeroMedia imagen={contenido.imagen} video={contenido.video} alt="" preload alto="completo" objectPosition={contenido.posicionImagen}>
        <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-between px-4 pb-10 pt-6 text-hero-ink sm:px-6 sm:pb-14 lg:px-12">
          {palabras.length > 0 ? <PalabraRota palabras={palabras} className="texto-gigante" /> : <span />}
          <div>
            <h1 className="texto-grande">{nombre}</h1>
            <div className="mt-6 flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
              <p className="max-w-[52ch] text-xl leading-snug">{contenido.subtitulo}</p>
              <Link href={`#${ANCLA_DE.reservar}`} className={botonClases({ variante: 'campana-claro' })}>
                {textos.cta}
              </Link>
            </div>
          </div>
        </div>
      </HeroMedia>
    </section>
  );
}
