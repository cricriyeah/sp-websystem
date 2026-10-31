import Image from 'next/image';
import type { SedePangas } from '@/content/sedes-tipos';
import type { LogoLargo } from '@/content/empresas-marca';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';
import { SelloTitulo } from '@/components/ui/sello-titulo';
import { fraseDeNombres } from '@/lib/frase-de-nombres';

type Props = {
  id: string;
  pangas: SedePangas;
  fondo: Fondo;
  /** Nombre de la empresa: el texto alternativo de su isotipo. */
  empresa: string;
  /** El isotipo (pez gallo y sol). */
  isotipo?: string;
  /** El isotipo transparente: con él, el sello va sin círculo blanco; sin él, el isotipo en su círculo. */
  isotipoSinFondo?: string;
  /** El logo largo a color: si la empresa lo tiene, va en la esquina en lugar del isotipo. */
  logoLargo?: LogoLargo;
};

/**
 * «Las pangas», justo bajo el héroe y antes de «Reservar ahora» (derivación PFD + Apple, 2026-10-30). Sin botón: lo
 * siguiente es lo que se reserva.
 *
 * Bajo el título (con el logo largo de la empresa en la esquina, del tamaño del sello y con el título bajado a su base para que quede pegado a la foto; sin él, el isotipo con `SelloTitulo`), la flota formada COMPLETA, en su proporción y sin nada
 * encima: el dueño la quiere entera y rechazó los nombres sobre la foto. Pegado a ella, el texto que la nombra en su orden
 * («De izquierda a derecha: …»), una sola frase y no siete rótulos. Al lado (escritorio) o debajo (teléfono), las pangas
 * navegando: en el teléfono es una tira que se desliza de lado con la siguiente asomándose, para que la sección no crezca
 * hacia abajo. En el teléfono la flota va de orilla a orilla. Server Component; entran con `rev`/`rev-foto`.
 */
export function PangasSede({ id, pangas, fondo, empresa, isotipo, isotipoSinFondo, logoLargo }: Props) {
  const { flota, fotos } = pangas;
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-24', CLASE_FONDO[fondo])}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-pagina sm:gap-10">
        <div className={cn('rev flex justify-between gap-6', logoLargo ? 'items-end' : 'items-start')}>
          <h2 id={`${id}-titulo`} className="texto-display m-0">{pangas.titulo}</h2>
          {logoLargo ? (
            <Image src={logoLargo.src} alt={empresa} width={logoLargo.ancho} height={logoLargo.alto} className="rev block h-12 w-auto shrink-0 sm:h-20 lg:h-24 xl:h-28" />
          ) : (
            isotipo && <SelloTitulo src={isotipoSinFondo ?? isotipo} alt={empresa} modo={isotipoSinFondo ? 'sin-aro' : 'aro-propio'} />
          )}
        </div>

        <div className="rev-foto -mx-[var(--margen-x)] sm:mx-0">
          <Image src={flota.src} alt={flota.alt} width={flota.ancho} height={flota.alto} sizes="(min-width: 1440px) 1376px, 100vw" className="block h-auto w-full" />
        </div>

        <div className="flex flex-col gap-8 lg:grid lg:grid-cols-12 lg:gap-x-6">
          <div className="rev flex flex-col gap-5 lg:col-span-5 lg:pr-6">
            <p className="texto-seccion m-0 font-semibold text-balance">{pangas.frase}</p>
            <p className="m-0 max-w-[48ch] text-lg leading-relaxed sm:text-xl">{pangas.texto.replace('{nombres}', fraseDeNombres(pangas.nombres, pangas.y))}</p>
          </div>
          <div className="-mx-[var(--margen-x)] flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-px-pagina px-pagina [scrollbar-width:none] sm:gap-4 lg:col-span-7 lg:mx-0 lg:grid lg:grid-cols-2 lg:gap-6 lg:overflow-visible lg:px-0 [&::-webkit-scrollbar]:hidden">
            {fotos.map((foto) => (
              <figure key={foto.src} className="rev-foto m-0 flex w-[82%] shrink-0 snap-start flex-col gap-2.5 sm:w-[60%] lg:w-auto">
                <div className="relative aspect-[4/3] overflow-hidden bg-tinta">
                  <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1024px) 28vw, 82vw" className="object-cover" />
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
