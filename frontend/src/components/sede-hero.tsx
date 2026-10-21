import Image from 'next/image';
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
  /** La empresa local que opera la sede; sin ella no hay sello. */
  empresa?: { nombre: string; logo?: string };
  textos: { cta: string; operadaPor: string };
};

/**
 * Arranque de campaña de una sede (F10): el video del mar a pantalla completa, desde el borde de
 * arriba (la barra flota encima), una palabra gigante que cambia con lo que se reserva ahí, el sello
 * de la empresa que opera, el nombre de la sede como `h1`, una frase y un solo botón que baja a lo que
 * se puede reservar. Lo comparten las tres sedes.
 *
 * El sello es una píldora blanca, el único bloque claro del arranque: así la empresa se lee antes que
 * el resto sin competir con el titular. Server Component (la palabra que rota es una isla cliente).
 */
export function SedeHero({ nombre, contenido, palabras, empresa, textos }: SedeHeroProps) {
  return (
    <section>
      <HeroMedia imagen={contenido.imagen} video={contenido.video} alt="" preload alto="completo" objectPosition={contenido.posicionImagen} objectPositionMovil={contenido.posicionImagenMovil}>
        <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-between gap-8 px-4 pb-10 pt-[calc(var(--nav-alto)+1.5rem)] text-hero-ink sm:px-6 sm:pb-14 lg:px-12">
          {palabras.length > 0 ? <PalabraRota palabras={palabras} className="texto-gigante" /> : <span />}
          <div>
            {empresa && (
              <p className="mb-6 inline-flex items-center gap-4 rounded-full bg-superficie py-2 pl-5 pr-6 text-foreground">
                {empresa.logo && (
                  <Image src={empresa.logo} alt="" width={120} height={40} className="h-10 w-auto max-w-32 object-contain" />
                )}
                <span className="flex flex-col">
                  <span className="texto-pie">{textos.operadaPor}</span>
                  <span className="texto-etiqueta">{empresa.nombre}</span>
                </span>
              </p>
            )}
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
