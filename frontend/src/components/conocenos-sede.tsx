import type { CSSProperties } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import type { SedeConocenos } from '@/content/sedes-tipos';
import type { LogoLargo } from '@/content/empresas-marca';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { capitanesVisibles, mostrarPendientesEnEsteEntorno } from '@/lib/capitanes-visibles';
import { ANCLA_DE } from '@/lib/secciones-sede';

type Props = {
  id: string;
  conocenos: SedeConocenos;
  fondo: Fondo;
  /** El logo largo a color de la empresa (`MarcaEmpresa.logoLargo`): cierra el relato, encima del botón. */
  logo?: LogoLargo;
  /** Nombre de la empresa: el texto alternativo del logo. */
  empresa: string;
};

/**
 * «Conócenos» de la sede: un solo relato a dos columnas, en un solo fondo (derivación PFD R1-R5 y taste, 2026-10-30;
 * reemplaza la banda tinta con el collage del staff y el cartel «Sal con el sol», que se leían como tres secciones).
 *
 * - Escritorio (lg): a la izquierda (columnas 1-5) las fotos del gremio bajan con la página: la del relato, la primera
 *   de `tripulacion.fotos` encimada y las demás (fotos de capitanes) en dos columnas escalonadas. No se alinean con ningún nombre ni cambian solas. A la derecha
 *   (7-12) el título, la apertura, los párrafos 1 y 2, los nombres de los capitanes como frase del relato justo después
 *   del párrafo que presenta al gremio, el párrafo 3 y el cierre: el logo largo a
 *   color de la empresa y debajo el único botón (el dueño quitó «Sal con el sol», el isotipo chico y la frase).
 * - Teléfono y tableta: una columna intercalada como revista con `order` (las dos columnas son `contents`): título,
 *   foto, párrafos 1-2, nombres, foto, párrafo 3, las fotos de capitanes (una grande y dos debajo) y cierre. Arriba de todo, a todo el ancho, `desde`: el año del gremio.
 *
 * Dinamismo (taste, 2026-10-30, el dueño lo veía plano): la columna de fotos no es una pila pareja. La del relato
 * sale de la retícula hasta el borde de la pantalla, la escena se encima sobre ella más angosta y separada por un
 * marco del color del fondo, y la pareja va escalonada; en el teléfono las dos grandes van de borde a borde. El título va en `texto-grande`. Atado al scroll (globals.css): las fotos derivan dentro de su marco
 * a dos velocidades, los nombres se entintan palabra por palabra al leerlos.
 *
 * Los capitanes `pendiente` no se publican; sin ninguno visible solo falta el renglón de nombres. El apodo va junto al
 * nombre, sin comillas (decisión del dueño). Con `ilustracion`, un dibujo (el dorado en La Paz) va de fondo, como el
 * logo de «Reserva con tranquilidad». Todo entra con `rev` al llegar a cuadro (con «reducir movimiento» no se
 * mueve). Server Component.
 */
/** El marco de la escena que se encima toma el color del fondo de la sección. */
const MARCO_DE: Record<Fondo, string> = { blanco: 'lg:outline-superficie', 'cafe-bruma': 'lg:outline-cafe-bruma', tinta: 'lg:outline-tinta' };

/** En el teléfono, de borde a borde de la pantalla; en escritorio solo sale por la izquierda, hasta el borde. */
const SANGRA = 'mx-[calc(var(--margen-x)*-1)] lg:mr-0';

export function ConocenosSede({ id, conocenos, fondo, logo, empresa }: Props) {
  const { titulo, apertura, historia, foto, desde, tripulacion, cierre, ilustracion } = conocenos;
  const capitanes = capitanesVisibles(tripulacion.capitanes, mostrarPendientesEnEsteEntorno(process.env));
  const [escena, ...resto] = tripulacion.fotos;
  // Dos columnas escalonadas: la de la derecha baja, así las fotos no forman una cuadrícula pareja.
  const columnas = [resto.filter((_, i) => i % 2 === 0), resto.filter((_, i) => i % 2 === 1)];
  // Bajo lg no hay columnas: con un número impar de fotos, la última va grande y primero, y las demás
  // en parejas debajo, para que no quede un hueco (pedido del dueño, 2026-11-05).
  const grande = resto.length % 2 === 1 ? resto[resto.length - 1] : undefined;

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('relative isolate scroll-mt-[calc(var(--nav-alto)+16px)] overflow-x-clip pt-16 pb-20 sm:pt-20 lg:pt-28 lg:pb-40', CLASE_FONDO[fondo])}>
      {ilustracion && (
        // Como el logo de fondo de «Reserva con tranquilidad»: grande, en tinta muy baja y cortado por el borde derecho,
        // detrás del relato. En el teléfono va bajo la primera foto (que lo taparía), detrás de los primeros párrafos.
        <span
          aria-hidden
          className="pointer-events-none absolute top-[29%] -right-[10%] -z-10 w-[145%] bg-contain bg-no-repeat opacity-[0.07] lg:top-[4%] lg:right-[4%] lg:w-[58%] lg:opacity-[0.06]"
          style={{ backgroundImage: `url(${ilustracion.src})`, aspectRatio: `${ilustracion.ancho} / ${ilustracion.alto}` }}
        />
      )}
      {desde && (
        // Lo primero de la sección y lo más visible (pedido del dueño, 2026-11-04): la frase y, a su derecha, el año
        // gigante, para que se lea de corrido («Más de 3 generaciones desde 1950», 2026-11-07). Todo en azules (dueño,
        // 2026-11-07): el año en azul; la frase y la raya gruesa punteada que lo separa del relato, del color del título
        // «Gente de mar» (foreground). La raya es un degradado y no `border-dashed`: el borde punteado deja huecos tan largos como el
        // trazo y el dueño los quiere cortos.
        <div className="rev mx-auto mb-12 max-w-[1440px] px-pagina sm:mb-16 lg:mb-24">
          <p
            // En el teléfono no hay raya (dueño, 2026-11-07): la imagen solo se aplica desde `sm`.
            style={{
              '--raya': 'repeating-linear-gradient(to right, var(--color-foreground) 0 28px, transparent 28px 36px)',
              backgroundSize: '100% 6px',
              backgroundPosition: 'left bottom',
              backgroundRepeat: 'no-repeat',
            } as CSSProperties}
            className="m-0 flex flex-col gap-3 pb-0 sm:pb-6 sm:[background-image:var(--raya)] font-[family-name:var(--font-titulo)] font-bold sm:flex-row sm:items-baseline-last sm:gap-10 lg:grid lg:grid-cols-12 lg:gap-x-6 lg:pb-8">
            {/* El año va sobre la base del último renglón de la frase. En desktop sigue la retícula del relato de abajo:
                la frase sobre las fotos y el año del ancho exacto de la columna de texto (cols. 7-12). `46.6cqi`: el
                «1950» mide 2.144 em en Consola Mono con su tracking, así que llena el contenedor. */}
            <span className="max-w-[14ch] text-3xl leading-[1.05] tracking-[0.04em] text-foreground sm:text-4xl lg:col-span-5 lg:text-6xl">{desde.texto}</span>
            {/* En el teléfono el año va a todo el ancho de la pantalla (dueño, 2026-11-07), con el mismo cálculo. */}
            <span className="max-sm:@container lg:@container lg:col-span-6 lg:col-start-7">
              <span className="texto-gigante block text-azul max-sm:text-[46.6cqi] lg:text-[46.6cqi]">{desde.anio}</span>
            </span>
          </p>
        </div>
      )}
      <div className="mx-auto flex max-w-[1440px] flex-col gap-7 px-pagina lg:grid lg:grid-cols-12 lg:items-start lg:gap-x-6">
        {/* Fotos del gremio */}
        <div className="contents lg:col-span-5 lg:flex lg:flex-col lg:gap-6">
          <Foto src={foto.src} alt={foto.alt} className={cn('order-2 aspect-[4/5] sm:aspect-[4/3] lg:order-none lg:aspect-[3/4]', SANGRA)} sizes="(min-width: 1024px) 42vw, 100vw" />
          {escena && (
            <Foto
              src={escena.src}
              alt={escena.alt}
              posicion={escena.posicion}
              rapida
              className={cn(
                'order-5 aspect-square lg:relative lg:z-[1] lg:order-none lg:-mt-[12%] lg:ml-auto lg:w-[78%] lg:outline-[24px] lg:outline-solid',
                SANGRA,
                MARCO_DE[fondo],
              )}
              sizes="(min-width: 1024px) 28vw, 90vw"
            />
          )}
          {resto.length > 0 && (
            <div className="order-7 grid grid-cols-2 items-start gap-3 sm:gap-5 lg:order-none lg:gap-6">
              {columnas.map((col, c) => (
                <div key={c} className={cn('contents lg:flex lg:flex-col lg:gap-6', c === 1 && 'lg:mt-[28%]')}>
                  {col.map((f, i) => (
                    <Foto
                      key={f.src}
                      src={f.src}
                      alt={f.alt}
                      posicion={f.posicion}
                      rapida={(c + i) % 2 === 1}
                      className={f === grande ? 'order-first col-span-2 aspect-[4/5] lg:order-none lg:col-span-1 lg:aspect-[3/4]' : 'aspect-[3/4]'}
                      sizes={f === grande ? '(min-width: 1024px) 19vw, 100vw' : '(min-width: 1024px) 19vw, 50vw'}
                    />
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Relato */}
        <div className="contents lg:col-span-6 lg:col-start-7 lg:flex lg:flex-col lg:gap-10">
          <div className="order-1 flex flex-col gap-6 lg:order-none">
            <h2 id={`${id}-titulo`} className="rev texto-grande m-0">
              {titulo}
            </h2>
            <p className="rev m-0 max-w-[32ch] text-2xl font-semibold leading-snug text-balance sm:text-3xl xl:text-4xl">{apertura}</p>
          </div>
          <Parrafos textos={historia.slice(0, 2)} className="order-3 lg:order-none" />
          {capitanes.length > 0 && (
            <div
              className={cn(
                'rev order-4 my-6 flex flex-col gap-8 px-7 py-9 text-tinta sm:my-8 sm:px-10 sm:py-12 lg:order-none lg:my-10 lg:px-12 lg:py-14',
                // Si la sección ya va en arena, el recuadro se perdería: ahí va en blanco.
                fondo === 'cafe-bruma' ? 'bg-superficie' : 'bg-arena',
              )}
            >
              {/* Pedido del dueño (2026-11-04): el staff resalta como bloque, en un recuadro con aire alrededor; desde
                  2026-11-07 en arena con letras y rayas oscuras (antes café). El título lleva una raya que corre hasta el
                  borde; el título va en azul y los capitanes en lista, cada uno con su apodo debajo, también en azul. */}
              <h3 className="m-0 flex items-center gap-5 font-[family-name:var(--font-titulo)] text-xl font-bold tracking-[0.18em] text-azul sm:text-2xl">
                <span className="shrink-0">{tripulacion.titulo}</span>
                <span aria-hidden className="h-px flex-1 bg-tinta/50" />
              </h3>
              <ul className="m-0 grid list-none grid-cols-1 gap-x-10 p-0 sm:grid-cols-2">
                {capitanes.map((c) => (
                  <li key={c.nombre} className="flex flex-col gap-2 border-t border-tinta/25 py-5">
                    <span className="texto-tripulacion leading-none">{c.nombre}</span>
                    {c.apodo && <span className="texto-tripulacion text-base tracking-[0.12em] text-azul sm:text-lg">{c.apodo}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Parrafos textos={historia.slice(2)} className="order-6 lg:order-none" />
          {/* Firma + acción (PFD, opción A, 2026-11-07): logo y botón a todo el ancho de la columna (el dueño no quiere
              nada a medio ancho), el botón con más presencia, así se leen como un solo bloque y no queda como nota al pie. */}
          <div className="rev order-9 flex flex-col gap-8 pt-6 lg:order-none lg:gap-6 lg:pt-10">
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

/** `overflow-clip` y no `hidden`: con `hidden` el marco sería un contenedor de scroll y la deriva no correría. También la usa `FamiliaSede`. */
export function Foto({ src, alt, className, sizes, rapida, posicion }: { src: string; alt: string; className: string; sizes: string; rapida?: boolean; posicion?: string }) {
  return (
    <div className={cn('rev-foto relative overflow-clip bg-tinta', className)}>
      <Image src={src} alt={alt} fill sizes={sizes} style={posicion ? { objectPosition: posicion } : undefined} className={cn('foto-deriva object-cover object-[50%_40%]', rapida && 'foto-deriva-rapida')} />
    </div>
  );
}

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
