import Image from 'next/image';
import type { SedePangas } from '@/content/sedes-tipos';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

type Props = {
  id: string;
  pangas: SedePangas;
  fondo: Fondo;
  /** Nombre de la empresa: el texto alternativo de su isotipo. */
  empresa: string;
  /** El isotipo (pez gallo y sol), en círculo blanco como en el resto de la página. */
  isotipo?: string;
};

/**
 * «Nuestras pangas», justo bajo el héroe (derivación PFD: el dueño quiere que sus pangas se vean al abrir, sin alejar lo
 * que se reserva). Cabe en una pantalla y no lleva botón: lo siguiente es «Reservar ahora».
 *
 * Arriba, el isotipo en círculo blanco junto al título («Las pangas de Sal y Sol»): la marca firma lo que es suyo, sin
 * etiqueta encima del título; debajo, una frase. Luego tres fotos: en escritorio la protagonista ocupa 7 columnas y las otras dos se apilan en las 5
 * restantes, a la misma altura; en el teléfono la protagonista va a todo el ancho y las dos de apoyo lado a lado. Cada
 * foto lleva debajo lo que muestra. Server Component; entran con `rev`/`rev-foto` al llegar a cuadro.
 */
export function PangasSede({ id, pangas, fondo, empresa, isotipo }: Props) {
  const [protagonista, ...apoyo] = pangas.fotos;
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-24', CLASE_FONDO[fondo])}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-pagina sm:gap-10">
        <div className="rev flex flex-col gap-4">
          <div className="flex items-center gap-4 sm:gap-5">
            {isotipo && (
              <span className="relative block size-14 shrink-0 overflow-hidden rounded-full bg-blanco sm:size-20">
                <Image src={isotipo} alt={empresa} fill sizes="80px" className="object-contain p-[6%]" />
              </span>
            )}
            <h2 id={`${id}-titulo`} className="texto-display m-0">{pangas.titulo}</h2>
          </div>
          <p className="texto-subtitulo m-0 max-w-[48ch]">{pangas.texto}</p>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-4 xl:grid-cols-12 xl:gap-x-6">
          {protagonista && (
            <figure className="rev-foto col-span-2 m-0 flex flex-col gap-2.5 xl:col-span-7">
              <div className="relative aspect-[4/3] overflow-hidden bg-tinta xl:aspect-auto xl:h-full xl:min-h-[34rem]">
                <Image src={protagonista.src} alt={protagonista.alt} fill sizes="(min-width: 1280px) 56vw, 100vw" className="object-cover object-[50%_60%]" />
              </div>
              <figcaption className="texto-pequeno">{protagonista.pie}</figcaption>
            </figure>
          )}
          <div className="col-span-2 grid grid-cols-2 gap-x-3 sm:gap-x-4 xl:col-span-5 xl:grid-cols-1 xl:gap-y-6">
            {apoyo.map((foto) => (
              <figure key={foto.src} className="rev-foto m-0 flex flex-col gap-2.5">
                <div className="relative aspect-square overflow-hidden bg-tinta xl:aspect-[16/9]">
                  <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1280px) 40vw, 50vw" className="object-cover object-[50%_45%]" />
                </div>
                <figcaption className="texto-pequeno">{foto.pie}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
