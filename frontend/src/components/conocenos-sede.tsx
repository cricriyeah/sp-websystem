import Image from 'next/image';
import Link from 'next/link';
import type { SedeConocenos } from '@/content/sedes-tipos';
import type { LogoLargo } from '@/content/empresas-marca';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { capitanesVisibles, mostrarPendientesEnEsteEntorno } from '@/lib/capitanes-visibles';
import { fraseDeNombres } from '@/lib/frase-de-nombres';
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
 *   de `tripulacion.fotos` y las otras dos lado a lado. No se alinean con ningún nombre ni cambian solas. A la derecha
 *   (7-12) el título, la apertura, los párrafos 1 y 2, los nombres de los capitanes como frase del relato justo después
 *   del párrafo que presenta al gremio, el párrafo 3, la prensa (el único bloque tinta) y el cierre: el logo largo a
 *   color de la empresa y debajo el único botón (el dueño quitó «Sal con el sol», el isotipo chico y la frase).
 * - Teléfono y tableta: una columna intercalada como revista con `order` (las dos columnas son `contents`): título,
 *   foto, párrafos 1-2, nombres, foto, párrafo 3, dos fotos, prensa y cierre.
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
  const { titulo, apertura, historia, foto, prensa, tripulacion, cierre, ilustracion } = conocenos;
  const capitanes = capitanesVisibles(tripulacion.capitanes, mostrarPendientesEnEsteEntorno(process.env));
  const [escena, ...pareja] = tripulacion.fotos;

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
      <div className="mx-auto flex max-w-[1440px] flex-col gap-7 px-pagina lg:grid lg:grid-cols-12 lg:items-start lg:gap-x-6">
        {/* Fotos del gremio */}
        <div className="contents lg:col-span-5 lg:flex lg:flex-col lg:gap-6">
          <Foto src={foto.src} alt={foto.alt} className={cn('order-2 aspect-[4/5] sm:aspect-[4/3] lg:order-none lg:aspect-[3/4]', SANGRA)} sizes="(min-width: 1024px) 42vw, 100vw" />
          {escena && (
            <Foto
              src={escena.src}
              alt={escena.alt}
              rapida
              className={cn(
                'order-5 aspect-[4/3] lg:relative lg:z-[1] lg:order-none lg:-mt-[12%] lg:ml-auto lg:w-[74%] lg:aspect-[4/5] lg:outline-[24px] lg:outline-solid',
                SANGRA,
                MARCO_DE[fondo],
              )}
              sizes="(min-width: 1024px) 28vw, 90vw"
            />
          )}
          {pareja.length > 0 && (
            <div className="order-7 grid grid-cols-2 items-start gap-3 lg:order-none lg:gap-6">
              {pareja.map((f, i) => (
                <Foto key={f.src} src={f.src} alt={f.alt} rapida={i === 1} className={cn('aspect-[4/5]', i === 1 && 'mt-[22%] lg:mt-[30%]')} sizes="(min-width: 1024px) 19vw, 50vw" />
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
            <p className="rev texto-tripulacion tinta-al-leer order-4 m-0 lg:order-none">
              {fraseDeNombres(
                capitanes.map((c) => (c.apodo ? `${c.nombre} ${c.apodo}` : c.nombre)),
                tripulacion.y,
              )
                .split(' ')
                .map((palabra, i) => (
                  <span key={i}>{i > 0 ? ` ${palabra}` : palabra}</span>
                ))}
            </p>
          )}
          <Parrafos textos={historia.slice(2)} className="order-6 lg:order-none" />
          <figure className="rev order-8 m-0 flex flex-col gap-3 bg-tinta p-6 text-hero-ink sm:p-8 lg:order-none">
            <figcaption className="texto-etiqueta">{prensa.etiqueta}</figcaption>
            <blockquote className="m-0 text-2xl font-semibold leading-snug text-balance xl:text-3xl">{`“${prensa.texto}”`}</blockquote>
            <p className="texto-cuerpo m-0">{prensa.fuente}</p>
          </figure>
          <div className="rev order-9 flex flex-col gap-8 pt-6 lg:order-none lg:pt-10">
            {logo && <Image src={logo.src} alt={empresa} width={logo.ancho} height={logo.alto} className="block h-auto w-full" />}
            <Link href={`#${ANCLA_DE.reservar}`} className={cn(botonClases({ variante: 'campana' }), 'w-full sm:w-auto sm:self-start')}>
              {cierre.boton}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

/** `overflow-clip` y no `hidden`: con `hidden` el marco sería un contenedor de scroll y la deriva no correría. */
function Foto({ src, alt, className, sizes, rapida }: { src: string; alt: string; className: string; sizes: string; rapida?: boolean }) {
  return (
    <div className={cn('rev-foto relative overflow-clip bg-tinta', className)}>
      <Image src={src} alt={alt} fill sizes={sizes} className={cn('foto-deriva object-cover object-[50%_40%]', rapida && 'foto-deriva-rapida')} />
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
