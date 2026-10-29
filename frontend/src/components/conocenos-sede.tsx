import Image from 'next/image';
import Link from 'next/link';
import type { SedeConocenos } from '@/content/sedes-tipos';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { capitanesVisibles, mostrarPendientesEnEsteEntorno } from '@/lib/capitanes-visibles';
import { ANCLA_DE } from '@/lib/secciones-sede';

type Props = {
  id: string;
  conocenos: SedeConocenos;
  fondo: Fondo;
  /** El isotipo de la empresa (el «pescadito»): la única marca que se repite en la tripulación. */
  isotipo?: string;
};

/**
 * «Conócenos» de la sede: la historia de su gente (taste, dirección editorial) y la derivación PFD (R1-R5).
 * Tres tiempos, cada uno con su propia composición:
 *
 * 1. Historia (relato editorial, sin cifras sueltas: se leían como estadísticas de ventas): en escritorio, la foto del
 *    gremio en las columnas 1-5, fija mientras se lee, y en las 6-12 el título, la frase de apertura grande (tamaño de
 *    frase, no de titular), los párrafos del relato con medida de lectura y la cita de prensa. El protagonista es el
 *    grupo; la foto nunca es el retrato de una sola persona. En el teléfono todo va apilado: título, apertura, foto,
 *    relato y prensa.
 * 2. Tripulación («One item per poster line»): el gremio como cartel, un nombre de pila por renglón en la letra de los
 *    titulares y, a la derecha y en la misma línea base, su dato con el isotipo delante (la única marca, la misma en
 *    todos). En escritorio el título se queda fijo a la izquierda mientras pasan los nombres (el movimiento firma de la
 *    hoja). Los capitanes `pendiente` no se publican; sin ninguno visible el bloque se omite.
 * 3. Cierre («The idea again, inverted»): campo tinta a todo el ancho, «Sal con el sol» en grande con el isotipo a su
 *    altura (el sol del logo es literal aquí) y el botón. Las fotos de las pangas viven en su propia sección, bajo el héroe.
 *
 * Todo entra con `rev` al llegar a cuadro (con «reducir movimiento» no se mueve). Server Component.
 */
export function ConocenosSede({ id, conocenos, fondo, isotipo }: Props) {
  const { titulo, apertura, historia, foto, prensa, tripulacion, cierre } = conocenos;
  const capitanes = capitanesVisibles(tripulacion.capitanes, mostrarPendientesEnEsteEntorno(process.env));

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] pt-16 sm:pt-20 lg:pt-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-24 px-pagina sm:gap-32 xl:gap-40">
        {/* 1. Historia */}
        <div className="grid gap-x-6 gap-y-10 xl:grid-cols-12">
          <div className="order-3 xl:order-none xl:col-span-5">
            <div className="rev-foto relative aspect-[4/3] overflow-hidden bg-tinta xl:sticky xl:top-[calc(var(--nav-alto)+2rem)] xl:aspect-[4/5]">
              <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1280px) 40vw, 100vw" className="object-cover object-[50%_35%]" />
            </div>
          </div>
          <div className="contents xl:col-span-7 xl:flex xl:flex-col xl:gap-10">
            <div className="order-1 flex flex-col gap-6 xl:order-none">
              <h2 id={`${id}-titulo`} className="rev texto-display m-0">
                {titulo}
              </h2>
              <p className="rev m-0 max-w-[32ch] text-2xl font-semibold leading-snug text-balance sm:text-3xl xl:text-4xl">{apertura}</p>
            </div>
            <div className="order-4 flex max-w-[62ch] flex-col gap-5 xl:order-none">
              {historia.map((parrafo) => (
                <p key={parrafo.slice(0, 32)} className="rev m-0 text-lg leading-relaxed sm:text-xl">
                  {parrafo}
                </p>
              ))}
            </div>
            <figure className="rev order-5 m-0 flex flex-col gap-3 bg-tinta p-6 text-hero-ink sm:p-8 xl:order-none">
              <figcaption className="texto-etiqueta">{prensa.etiqueta}</figcaption>
              <blockquote className="m-0 text-2xl font-semibold leading-snug text-balance xl:text-3xl">{`“${prensa.texto}”`}</blockquote>
              <p className="texto-cuerpo m-0">{prensa.fuente}</p>
            </figure>
          </div>
        </div>

        {/* 2. Tripulación */}
        {capitanes.length > 0 && (
          <div className="grid gap-x-6 gap-y-10 xl:grid-cols-12">
            <div className="xl:col-span-4">
              <div className="rev flex flex-col gap-4 xl:sticky xl:top-[calc(var(--nav-alto)+2rem)]">
                <h3 className="texto-pagina m-0">{tripulacion.titulo}</h3>
                <p className="texto-subtitulo m-0 max-w-[30ch]">{tripulacion.texto}</p>
              </div>
            </div>
            <ul className="m-0 flex list-none flex-col gap-5 p-0 sm:gap-2 xl:col-span-8">
              {capitanes.map((capitan) => (
                <li key={capitan.nombre} className="rev flex flex-col gap-1.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
                  <span className="texto-tripulacion">{capitan.nombre}</span>
                  {capitan.detalle && (
                    <span className="flex items-center gap-2.5 text-[16px] leading-snug sm:shrink-0 sm:text-[20px]">
                      {isotipo && (
                        <span aria-hidden className="relative block size-7 shrink-0 overflow-hidden rounded-full bg-blanco sm:size-8">
                          <Image src={isotipo} alt="" fill sizes="32px" className="object-contain p-[6%]" />
                        </span>
                      )}
                      {capitan.detalle}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 3. Cierre: la idea otra vez, con los colores al revés */}
      <div className="mt-24 bg-tinta text-hero-ink sm:mt-32 xl:mt-40">
        <div className="mx-auto flex min-h-[60svh] max-w-[1440px] flex-col justify-between gap-16 px-pagina py-16 sm:py-20">
          <div className="rev flex items-start justify-between gap-6">
            <p className="texto-gigante m-0 max-w-[9ch]">{cierre.titulo}</p>
            {isotipo && (
              <span aria-hidden className="relative block size-24 shrink-0 overflow-hidden rounded-full bg-blanco sm:size-40 xl:size-56">
                <Image src={isotipo} alt="" fill sizes="(min-width: 1280px) 224px, (min-width: 640px) 160px, 96px" className="object-contain p-[6%]" />
              </span>
            )}
          </div>
          <div className="rev flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <p className="m-0 max-w-[40ch] text-xl leading-snug">{cierre.frase}</p>
            <Link href={`#${ANCLA_DE.reservar}`} className={cn(botonClases({ variante: 'campana-claro' }), 'w-full sm:w-auto')}>
              {cierre.boton}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
