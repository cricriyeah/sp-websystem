import type { CSSProperties } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import type { SedeFamilia } from '@/content/sedes-tipos';
import type { LogoLargo } from '@/content/empresas-marca';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { Foto } from '@/components/conocenos-sede';
import { ANCLA_DE } from '@/lib/secciones-sede';

type Props = {
  id: string;
  familia: SedeFamilia;
  fondo: Fondo;
  /** El logo largo de la empresa: firma el relato a todo el ancho de la columna, encima del botón. */
  logo?: LogoLargo;
  empresa: string;
};

/** El marco del retrato encimado toma el color del fondo de la sección (como la escena de «Gente de mar»). */
const MARCO_DE: Record<Fondo, string> = { blanco: 'lg:outline-superficie', 'cafe-bruma': 'lg:outline-cafe-bruma', tinta: 'lg:outline-tinta' };
/** En el teléfono, de borde a borde; en escritorio solo sale por la izquierda. */
const SANGRA = 'mx-[calc(var(--margen-x)*-1)] lg:mr-0';
/** La raya gruesa punteada bajo la cifra, la misma de La Paz (un degradado: el borde punteado deja huecos largos). */
// Coral en vez de azul (dueño, 2026-11-12): el coral solo pasa 3:1 en blanco, así que va en la cifra y el título del
// recuadro (texto grande) y los datos chicos van en coral hondo.
const RAYA = {
  '--raya': 'repeating-linear-gradient(to right, var(--color-foreground) 0 28px, transparent 28px 36px)',
  backgroundSize: '100% 6px',
  backgroundPosition: 'left bottom',
  backgroundRepeat: 'no-repeat',
} as CSSProperties;

function Parrafos({ textos, className }: { textos: string[]; className: string }) {
  if (textos.length === 0) return null;
  return (
    <div className={cn('flex max-w-[62ch] flex-col gap-5', className)}>
      {textos.map((parrafo) => (
        <p key={parrafo.slice(0, 32)} className="rev m-0 text-lg leading-relaxed sm:text-xl">
          {parrafo}
        </p>
      ))}
    </div>
  );
}

/**
 * «Conócenos» de una empresa familiar (Puerto Chale). Rehecha el 2026-11-12: el dueño no quería un acomodo de datos sino
 * un relato emocional como «Gente de mar» de La Paz, y no quería el retrato estirado (la foto mide 896 px y se pixelaba).
 *
 * Misma gramática que la de La Paz, al revés en la cifra para no ser su copia:
 * - Arriba, la cifra gigante en coral («+5») como letra capitular y su frase pegada a la derecha (apiladas en el
 *   teléfono), con la raya punteada debajo. Se lee de corrido: «+5 generaciones de pescadores en Bahía Magdalena».
 * - Escritorio: a la izquierda (cols. 1-5) las ballenas junto a la panga salen hasta el borde; encima, más angosto y con
 *   marco del color del fondo, el retrato de Cristian (a un tamaño donde su foto no se estira); debajo, dos fotos
 *   escalonadas. A la derecha (7-12) el título, la frase grande, dos párrafos, «Quién te lleva» en un recuadro (el
 *   nombre en grande y sus datos), el último párrafo, el logo y el único botón.
 * - Teléfono: una columna intercalada con `order` (las columnas son `contents`).
 *
 * Las fotos derivan dentro de su marco al hacer scroll y todo entra con `rev` (quieto con «reducir movimiento»).
 * Server Component.
 */
export function FamiliaSede({ id, familia, fondo, logo, empresa }: Props) {
  const { desde, titulo, apertura, historia, foto, retrato, fotos, quien, cierre } = familia;
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('relative isolate scroll-mt-[calc(var(--nav-alto)+16px)] overflow-x-clip pt-16 pb-20 sm:pt-20 lg:pt-28 lg:pb-40', CLASE_FONDO[fondo])}>
      <div className="rev mx-auto mb-12 max-w-[1440px] px-pagina sm:mb-16 lg:mb-24">
        {/* PFD (2026-11-12, el dueño la veía partida): cifra y frase son una sola oración, así que la frase empieza
            donde termina la cifra. Desde `sm`, el «+5» como letra capitular y la frase pegada a su derecha, sobre su
            pie; en el teléfono, apiladas (en fila el «+» se separaba del «5»). */}
        <p
          style={RAYA}
          className="m-0 flex flex-col gap-3 font-[family-name:var(--font-titulo)] font-bold sm:flex-row sm:items-end sm:gap-[clamp(1rem,2.2vw,2.5rem)] sm:pb-6 sm:[background-image:var(--raya)] lg:pb-8"
        >
          <span className="texto-gigante shrink-0 whitespace-nowrap text-coral text-[clamp(7rem,17vw,16rem)] leading-[0.78]">{desde.cifra}</span>
          <span className="max-w-[22ch] text-3xl leading-[1.05] tracking-[0.04em] text-foreground sm:pb-[0.1em] sm:text-[clamp(1.6rem,3.6vw,3.75rem)]">{desde.texto}</span>
        </p>
      </div>

      <div className="mx-auto flex max-w-[1440px] flex-col gap-7 px-pagina lg:grid lg:grid-cols-12 lg:items-start lg:gap-x-6">
        {/* Fotos */}
        <div className="contents lg:col-span-5 lg:flex lg:flex-col lg:gap-6">
          <Foto src={foto.src} alt={foto.alt} posicion={foto.posicion} className={cn('order-2 aspect-[4/5] lg:order-none lg:aspect-[3/4]', SANGRA)} sizes="(min-width: 1024px) 42vw, 100vw" />
          <Foto
            src={retrato.src}
            alt={retrato.alt}
            posicion={retrato.posicion}
            rapida
            className={cn('order-5 aspect-[4/5] lg:relative lg:z-[1] lg:order-none lg:-mt-[18%] lg:ml-auto lg:w-[68%] lg:outline-[24px] lg:outline-solid', SANGRA, MARCO_DE[fondo])}
            sizes="(min-width: 1024px) 26vw, 100vw"
          />
          {fotos.length > 0 && (
            <div className="order-8 grid grid-cols-2 items-start gap-3 sm:gap-5 lg:order-none lg:gap-6">
              {fotos.map((f, i) => (
                <Foto key={f.src} src={f.src} alt={f.alt} posicion={f.posicion} rapida={i % 2 === 1} className={cn('aspect-[3/4]', i % 2 === 1 && 'lg:mt-[28%]')} sizes="(min-width: 1024px) 19vw, 50vw" />
              ))}
            </div>
          )}
        </div>

        {/* Relato */}
        <div className="contents lg:col-span-6 lg:col-start-7 lg:flex lg:flex-col lg:gap-10">
          <div className="order-1 flex flex-col gap-6 lg:order-none">
            <h2 id={`${id}-titulo`} className="rev texto-grande m-0">{titulo}</h2>
            <p className="rev m-0 max-w-[32ch] text-2xl font-semibold leading-snug text-balance sm:text-3xl xl:text-4xl">{apertura}</p>
          </div>
          <Parrafos textos={historia.slice(0, 2)} className="order-3 lg:order-none" />

          <div className={cn('rev order-6 my-6 flex flex-col gap-6 px-7 py-9 text-tinta sm:my-8 sm:px-10 sm:py-12 lg:order-none lg:my-10 lg:px-12 lg:py-14', fondo === 'cafe-bruma' ? 'bg-superficie' : 'bg-arena')}>
            <h3 className="m-0 flex items-center gap-5 font-[family-name:var(--font-titulo)] text-xl font-bold tracking-[0.18em] text-coral sm:text-2xl">
              <span className="shrink-0">{quien.titulo}</span>
              <span aria-hidden className="h-px flex-1 bg-tinta/50" />
            </h3>
            <p className="m-0 texto-tripulacion leading-none">{quien.nombre}</p>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {quien.detalles.map((d) => (
                <li key={d} className="texto-tripulacion text-base tracking-[0.12em] text-coral-hondo sm:text-lg">{d}</li>
              ))}
            </ul>
          </div>

          <Parrafos textos={historia.slice(2)} className="order-7 lg:order-none" />

          <div className="rev order-10 flex flex-col gap-8 pt-6 lg:order-none lg:gap-6 lg:pt-6">
            {logo && <Image src={logo.src} alt={empresa} width={logo.ancho} height={logo.alto} className="block h-auto w-full" />}
            <Link href={`#${ANCLA_DE.reservar}`} className={cn(botonClases({ variante: 'campana' }), 'w-full sm:w-auto sm:self-start lg:w-full lg:py-5 lg:text-lg')}>
              {cierre.boton}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
