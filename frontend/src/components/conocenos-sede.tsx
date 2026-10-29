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
 * Cuatro tiempos, cada uno con su propia composición:
 *
 * 1. Reseña («Side facts, wide paragraph»): el título; a la izquierda (34 %) los tres hechos, cada cifra monumental
 *    con lo que cuenta debajo;
 *    desde la misma línea, la reseña a lo ancho. Abajo, «Prensa» y la cita, en la misma retícula.
 * 2. Tripulación («One item per poster line»): el gremio como cartel, un nombre de pila por renglón en la letra de los
 *    titulares y, a la derecha y en la misma línea base, su dato con el isotipo delante (la única marca, la misma en
 *    todos). En escritorio el título se queda fijo a la izquierda mientras pasan los nombres (el movimiento firma de la
 *    hoja). Los capitanes `pendiente` no se publican; sin ninguno visible el bloque se omite.
 * 3. Fotos («Staggered pairs in empty ground»): de dos en dos, a tamaños y alturas distintas, cada una con lo que muestra.
 * 4. Cierre («The idea again, inverted»): campo tinta a todo el ancho, «Sal con el sol» en grande y el botón.
 *
 * Todo entra con `rev` al llegar a cuadro (con «reducir movimiento» no se mueve). Server Component.
 */
export function ConocenosSede({ id, conocenos, fondo, isotipo }: Props) {
  const { titulo, hechos, resena, prensa, tripulacion, fotos, cierre } = conocenos;
  const capitanes = capitanesVisibles(tripulacion.capitanes, mostrarPendientesEnEsteEntorno(process.env));
  const pares = Array.from({ length: Math.ceil(fotos.length / 2) }, (_, i) => fotos.slice(i * 2, i * 2 + 2));

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] pt-16 sm:pt-20 lg:pt-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-24 px-pagina sm:gap-32 xl:gap-40">
        {/* 1. Reseña */}
        <div className="grid gap-x-6 gap-y-10 xl:grid-cols-12 xl:gap-y-16">
          <h2 id={`${id}-titulo`} className="rev texto-display m-0 xl:col-span-12">
            {titulo}
          </h2>
          <dl className="m-0 grid grid-cols-3 gap-x-4 gap-y-6 sm:gap-x-6 xl:col-span-4 xl:grid-cols-1 xl:gap-y-10">
            {hechos.map((h) => (
              <div key={h.etiqueta} className="rev flex flex-col-reverse gap-1">
                <dt className="texto-pequeno max-w-[24ch] sm:text-base">{h.etiqueta}</dt>
                <dd className="texto-destacado m-0 text-cafe">{h.valor}</dd>
              </div>
            ))}
          </dl>
          <p className="rev m-0 text-xl leading-[1.4] sm:text-2xl xl:col-span-8">{resena}</p>
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

        {/* 3. Fotos, de dos en dos */}
        <div className="flex flex-col gap-12 xl:gap-16">
          {pares.map((par, i) => (
            <div key={par[0].src} className="flex flex-col gap-16 xl:grid xl:grid-cols-12 xl:gap-x-6 xl:gap-y-0">
              {par.map((foto, j) => (
                <figure key={foto.src} className={cn('rev-foto m-0 flex flex-col gap-2.5', FORMA[(i % 2) * 2 + j])}>
                  <div className={cn('relative overflow-hidden bg-tinta', PROPORCION[(i % 2) * 2 + j])}>
                    <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1280px) 50vw, 90vw" className="object-cover" />
                  </div>
                  <figcaption className="texto-pequeno">{foto.pie}</figcaption>
                </figure>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* 4. Cierre: la idea otra vez, con los colores al revés */}
      <div className="mt-24 bg-tinta text-hero-ink sm:mt-32 xl:mt-40">
        <div className="mx-auto flex min-h-[60svh] max-w-[1440px] flex-col justify-between gap-16 px-pagina py-16 sm:py-20">
          <p className="rev texto-gigante m-0 max-w-[9ch]">{cierre.titulo}</p>
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

/*
 * Las dos formas de par de la hoja, en el teléfono y en escritorio:
 *  A) retrato 3:4 en las columnas 1-4 contra el margen izquierdo y, 10 rem más abajo, una 5:4 en las 7-12 contra el derecho;
 *  B) apaisada 3:2 en las 6-11 y, 6 rem más abajo, una 4:5 chica en las 2-4.
 * En el teléfono alternan ancho y lado: 70 % a la izquierda, 84 % a la derecha, 56 % a la izquierda, todo el ancho.
 */
const FORMA = [
  'w-[70%] xl:w-auto xl:col-span-4 xl:col-start-1 xl:row-start-1',
  'ml-auto w-[84%] xl:ml-0 xl:w-auto xl:col-span-6 xl:col-start-7 xl:row-start-1 xl:mt-40',
  'w-[56%] xl:w-auto xl:col-span-6 xl:col-start-6 xl:row-start-1',
  'w-full xl:w-auto xl:col-span-3 xl:col-start-2 xl:row-start-1 xl:mt-24',
];

const PROPORCION = ['aspect-[3/4]', 'aspect-[5/4]', 'aspect-[3/2]', 'aspect-[4/5]'];
