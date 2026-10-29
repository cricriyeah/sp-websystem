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
 * «Conócenos» de la sede, rehecho con la dirección de taste «El nombre como monumento» y la derivación PFD (R1-R5).
 * Tres tiempos, cada uno con su propia composición:
 *
 * 1. Reseña («Side facts, wide paragraph»): el título; a la izquierda (34 %) los tres hechos, cada cifra monumental
 *    con lo que cuenta debajo; desde la misma línea, la reseña a lo ancho y, bajo ella, la foto de la panga del jefe (la
 *    Dream), que cierra la columna a la altura de la última cifra (sin ella, la mitad derecha quedaba vacía). Abajo,
 *    «Prensa» y la cita, en la misma retícula.
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
  const { titulo, hechos, resena, foto, prensa, tripulacion, cierre } = conocenos;
  const capitanes = capitanesVisibles(tripulacion.capitanes, mostrarPendientesEnEsteEntorno(process.env));

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] pt-16 sm:pt-20 lg:pt-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-24 px-pagina sm:gap-32 xl:gap-40">
        {/* 1. Reseña */}
        <div className="grid gap-x-6 gap-y-10 xl:grid-cols-12 xl:gap-y-16">
          <h2 id={`${id}-titulo`} className="rev texto-display m-0 xl:col-span-12">
            {titulo}
          </h2>
          <dl className="m-0 grid grid-cols-3 gap-x-4 gap-y-6 sm:gap-x-6 xl:col-span-4 xl:row-span-2 xl:grid-cols-1 xl:content-between xl:gap-y-10">
            {hechos.map((h) => (
              <div key={h.etiqueta} className="rev flex flex-col-reverse gap-1">
                <dt className="texto-pequeno max-w-[24ch] sm:text-base">{h.etiqueta}</dt>
                <dd className="texto-destacado m-0 text-cafe">{h.valor}</dd>
              </div>
            ))}
          </dl>
          <p className="rev m-0 text-xl leading-[1.4] sm:text-2xl xl:col-span-8">{resena}</p>
          <div className="rev-foto relative aspect-[2/1] overflow-hidden bg-tinta xl:col-span-8 xl:col-start-5">
            <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1280px) 60vw, 100vw" className="object-cover object-[20%_55%]" />
          </div>
          <p className="rev texto-etiqueta m-0 xl:col-span-4">{prensa.etiqueta}</p>
          <figure className="rev m-0 flex flex-col gap-3 xl:col-span-8">
            <blockquote className="m-0 max-w-[36ch] text-2xl font-semibold leading-snug text-balance xl:text-3xl">{`“${prensa.texto}”`}</blockquote>
            <figcaption className="texto-cuerpo">{prensa.fuente}</figcaption>
          </figure>
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
