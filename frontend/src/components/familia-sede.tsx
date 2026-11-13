import Link from 'next/link';
import type { SedeFamilia } from '@/content/sedes-tipos';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { Foto } from '@/components/conocenos-sede';
import { LineaTemporada } from '@/components/linea-temporada';
import { ANCLA_DE } from '@/lib/secciones-sede';

type Props = {
  id: string;
  familia: SedeFamilia;
  fondo: Fondo;
};

/**
 * En el teléfono las dos fotos van de borde a borde. En escritorio cada una sale solo por su orilla (el retrato por la
 * izquierda, las ballenas por la derecha), así el marco queda parejo de los dos lados.
 */
const SANGRA_IZQUIERDA = 'mx-[calc(var(--margen-x)*-1)] lg:mr-0';
const SANGRA_DERECHA = 'mx-[calc(var(--margen-x)*-1)] lg:ml-0';

/** Las dos fotos miden lo mismo de alto en escritorio, y la fila completa cabe en una pantalla bajo el título. */
const ALTO = 'lg:h-[min(34rem,calc(100svh-var(--nav-alto)-15rem))] lg:min-h-[24rem]';
const ALTO_FILA = cn('lg:aspect-auto', ALTO);
/** La columna de texto mide lo mismo que las fotos, pero crece si en una pantalla baja no le alcanza. */
const ALTO_TEXTO = 'lg:min-h-[max(24rem,min(34rem,calc(100svh-var(--nav-alto)-15rem)))]';

/**
 * «Conócenos» de una empresa familiar (Puerto Chale; PFD + taste, rehecha el 2026-11-10 porque en escritorio ocupaba
 * casi tres pantallas y la cara de Cristian llegaba al último).
 *
 * - Escritorio: el título a todo el ancho y, debajo, una sola fila que cabe en la pantalla: el retrato (izquierda),
 *   las palabras (en medio, la columna más ancha: quiénes son arriba; nombre, años, temporada y el botón abajo,
 *   alineado con el pie de las fotos) y la prueba (derecha: las ballenas junto a su panga, con su pie). La persona y lo que hace se ven juntas.
 * - Teléfono: una columna en orden de lectura con `order` (las columnas son `contents`): título, quiénes son,
 *   retrato con nombre y años, ballenas, temporada y botón.
 *
 * Un solo botón, con el mismo nombre que en el resto del sitio. Entra con `rev` y las fotos derivan al hacer scroll
 * (quieto con «reducir movimiento»). Server Component; la línea de temporada es la única pieza de cliente.
 */
export function FamiliaSede({ id, familia, fondo }: Props) {
  const { titulo, apertura, retrato, nombre, anios, foto, temporada, cierre } = familia;
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('relative isolate scroll-mt-[calc(var(--nav-alto)+16px)] overflow-x-clip py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-pagina lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_minmax(0,1fr)] lg:items-stretch lg:gap-x-8 lg:gap-y-12">
        {/* En el teléfono baja a 8.2vw para que el título no pase de dos renglones. */}
        <h2 id={`${id}-titulo`} className="rev texto-grande order-1 m-0 max-sm:text-[8.2vw] lg:order-none lg:col-span-full">
          {titulo}
        </h2>

        {/* La persona */}
        <figure className="order-3 m-0 flex flex-col gap-4 lg:order-none">
          <Foto src={retrato.src} alt={retrato.alt} posicion={retrato.posicion} className={cn('aspect-[4/5]', ALTO_FILA, SANGRA_IZQUIERDA)} sizes="(min-width: 1024px) 32vw, 100vw" />
          {/* En escritorio el nombre va en la columna de en medio; aquí solo para el teléfono. */}
          <figcaption className="rev flex flex-col gap-2 lg:hidden">
            <span className="texto-tripulacion leading-none">{nombre}</span>
            <span className="text-lg font-semibold text-azul sm:text-xl">{anios}</span>
          </figcaption>
        </figure>

        {/* Las palabras: arriba quiénes son, abajo quién te lleva y la acción, pegada al pie de las fotos */}
        <div className={cn('contents lg:flex lg:flex-col lg:justify-between lg:gap-6 lg:self-start', ALTO_TEXTO)}>
          <p className="rev order-2 m-0 text-2xl font-semibold leading-snug text-balance sm:text-3xl lg:order-none lg:text-2xl xl:text-[1.75rem]">{apertura}</p>
          <div className="order-5 flex flex-col gap-8 lg:order-none lg:gap-5">
            <p className="rev m-0 hidden flex-col gap-2 lg:flex">
              <span className="texto-tripulacion leading-none">{nombre}</span>
              <span className="text-xl font-semibold text-azul">{anios}</span>
            </p>
            {temporada && <LineaTemporada {...temporada} className="rev m-0 text-lg font-semibold text-azul sm:text-xl lg:text-lg" />}
            <Link href={`#${ANCLA_DE.reservar}`} className={cn(botonClases({ variante: 'campana' }), 'rev w-full sm:w-auto sm:self-start lg:px-10 lg:py-5 lg:text-lg')}>
              {cierre.boton}
            </Link>
          </div>
        </div>

        {/* La prueba */}
        <figure className="order-4 m-0 flex flex-col gap-4 lg:order-none">
          <Foto src={foto.src} alt={foto.alt} posicion={foto.posicion} rapida className={cn('aspect-[4/5]', ALTO_FILA, SANGRA_DERECHA)} sizes="(min-width: 1024px) 32vw, 100vw" />
          <figcaption className="rev text-base sm:text-lg">{foto.pie}</figcaption>
        </figure>
      </div>
    </section>
  );
}
