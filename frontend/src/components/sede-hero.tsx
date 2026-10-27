import Link from 'next/link';
import type { SedeHeroContenido } from '@/content/sedes-tipos';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { PalabraRota } from '@/components/palabra-rota';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';

type SedeHeroProps = {
  nombre: string;
  contenido: SedeHeroContenido;
  /** Lo que vende la sede, sacado de su catálogo (`palabrasDeSede`); vacío si el catálogo no respondió. */
  palabras: string[];
  /** La empresa local que opera la sede; sin ella no hay sello. */
  empresa?: { nombre: string; logo?: string; simbolo?: string };
  textos: { cta: string; operadaPor: string };
};

/**
 * Arranque de campaña de una sede (F10): el video del mar a pantalla completa, desde el borde de
 * arriba (la barra flota encima), una palabra gigante que cambia con lo que se reserva ahí, el sello
 * de la empresa que opera, el nombre de la sede como `h1`, una frase y un solo botón que baja a lo que
 * se puede reservar. Lo comparten las tres sedes.
 *
 * La empresa va justo debajo del nombre, en una sola línea: su símbolo suelto, sin círculo y sin letras, y
 * «Con <nombre>» a tamaño de frase. Sin etiqueta ni píldora: se lee de corrido con el titular. Server Component (la palabra que rota es una isla cliente).
 */
export function SedeHero({ nombre, contenido, palabras, empresa, textos }: SedeHeroProps) {
  return (
    <section>
      <HeroMedia imagen={contenido.imagen} video={contenido.video} alt="" preload alto="completo" objectPosition={contenido.posicionImagen} objectPositionMovil={contenido.posicionImagenMovil}>
        <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-between gap-8 px-4 pb-10 pt-[calc(var(--nav-alto)+1.5rem)] text-hero-ink sm:px-6 sm:pb-14 lg:px-12">
          {palabras.length > 0 ? <PalabraRota palabras={palabras} className="texto-gigante" /> : <span />}
          <div>
            <h1 className="texto-grande">{nombre}</h1>
            {empresa && (
              <div className="mt-6 flex items-center gap-4">
                <EmpresaSello nombre={empresa.nombre} logo={empresa.simbolo ?? empresa.logo} tamano={64} sinCirculo />
                <p className="text-2xl font-semibold leading-tight">
                  <span className="font-normal">{textos.operadaPor}</span> {empresa.nombre}
                </p>
              </div>
            )}
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
