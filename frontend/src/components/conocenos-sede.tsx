import Image from 'next/image';
import Link from 'next/link';
import type { SedeConocenos } from '@/content/sedes-tipos';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { capitanesVisibles, mostrarPendientesEnEsteEntorno } from '@/lib/capitanes-visibles';
import { iniciales } from '@/lib/iniciales';
import { ANCLA_DE } from '@/lib/secciones-sede';

type Props = {
  id: string;
  conocenos: SedeConocenos;
  fondo: Fondo;
};

/**
 * «Conócenos»: quién lleva el negocio, de arriba abajo en cinco bloques.
 *
 * 1. El título en tres líneas (la del medio, «generaciones», un tamaño por encima y en el acento) y la apertura.
 * 2. El mosaico «foto ancha + campo de color»: la foto en las columnas 1-8 (con su proporción nativa 2:1, no se recorta:
 *    se ven el capitán y el nombre de la panga) y, de su misma altura, un campo tinta en las 9-12 con las dos cifras que
 *    el dueño confirmó (los años de Rogelio en el mar y las generaciones de su familia), lo más grande de la sección.
 * 3. Los socios, en dos columnas.
 * 4. El gremio de capitanes: un círculo por capitán, todos iguales (la misma foto en círculo, el mismo nombre debajo)
 *    y con UN solo sello: el aro del sol del logo (`border-sol`). No hay estrellas ni insignias: lo que distingue al
 *    gremio es que son capitanes de aquí, y eso lo dice el texto. Los capitanes `pendiente` (relleno) no se pintan en el
 *    sitio publicado; sin ninguno visible, el bloque entero se omite (`capitanesVisibles`).
 * 5. La flota (tres fotos de pangas a tres tamaños, con un pie común) y el cierre: la cita de prensa sobre un campo tinta
 *    y el botón de reservar, para que quien llegó hasta aquí tenga la acción a la mano.
 *
 * Todo entra con `rev` (en el orden en que se lee; con «reducir movimiento» no se mueve). Server Component.
 */
export function ConocenosSede({ id, conocenos, fondo }: Props) {
  const { titulo, apertura, foto, cifras, socios, gremio, flota, cita, reservar } = conocenos;
  const capitanes = capitanesVisibles(gremio.capitanes, mostrarPendientesEnEsteEntorno(process.env));
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto grid max-w-[1440px] gap-x-6 gap-y-10 px-pagina xl:grid-cols-12 xl:gap-y-14">
        <h2 id={`${id}-titulo`} className="rev texto-grande xl:col-span-12">
          <span className="block">{titulo.inicio}</span>{' '}
          <span className="block texto-destacado text-cafe">{titulo.destacada}</span>{' '}
          <span className="block">{titulo.fin}</span>
        </h2>

        <p className="rev max-w-[26ch] text-2xl font-semibold leading-snug text-balance sm:text-3xl xl:col-span-6 xl:max-w-[30ch] xl:text-4xl">{apertura}</p>

        <div className="rev-foto relative aspect-[2912/1464] overflow-hidden bg-tinta xl:col-span-8">
          <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1280px) 66vw, 100vw" className="object-cover" />
        </div>

        <ul className="rev m-0 flex list-none flex-col justify-center gap-8 bg-tinta p-6 text-hero-ink sm:flex-row sm:gap-10 sm:p-8 xl:col-span-4 xl:flex-col xl:gap-10">
          {cifras.map((cifra) => (
            <li key={cifra.valor} className="sm:flex-1 xl:flex-none">
              <span className="texto-destacado block text-sol">{cifra.valor}</span>
              <span className="mt-3 block max-w-[22ch] text-xl font-semibold leading-snug">{cifra.texto}</span>
            </li>
          ))}
        </ul>

        <ul className="grid gap-8 sm:grid-cols-2 sm:gap-6 xl:col-span-12">
          {socios.map((socio) => (
            <li key={socio.nombre} className="rev">
              <strong className="block text-xl font-semibold leading-snug">{socio.nombre}</strong>
              <span className="mt-3 block max-w-[60ch] texto-cuerpo">{socio.texto}</span>
            </li>
          ))}
        </ul>

        {capitanes.length > 0 && (
          <div className="grid gap-8 xl:col-span-12 xl:grid-cols-12 xl:gap-6">
            <div className="rev flex flex-col gap-4 xl:col-span-5">
              <h3 className="texto-pagina text-balance">{gremio.titulo}</h3>
              <p className="texto-subtitulo max-w-[40ch]">{gremio.texto}</p>
            </div>
            <ul className="m-0 grid list-none grid-cols-3 gap-x-4 gap-y-8 p-0 sm:gap-x-8 xl:col-span-7">
              {capitanes.map((capitan, i) => (
                <li key={capitan.nombre} className="rev" style={{ animationDelay: `${Math.min(i, 9) * 60}ms` }}>
                  <span className="relative mx-auto block aspect-square w-full max-w-40 overflow-hidden rounded-full border-[5px] border-sol bg-tinta">
                    {capitan.foto ? (
                      <Image src={capitan.foto} alt={capitan.alt ?? capitan.nombre} fill sizes="(min-width: 640px) 160px, 30vw" className="object-cover" />
                    ) : (
                      <span aria-hidden className="flex size-full items-center justify-center font-display text-3xl font-bold text-hero-ink">
                        {iniciales(capitan.nombre)}
                      </span>
                    )}
                  </span>
                  <span className="texto-etiqueta mx-auto mt-3 block max-w-40 text-center text-balance">{capitan.nombre}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-col gap-4 xl:col-span-12">
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-12 xl:gap-6">
            {flota.fotos.map((f, i) => (
              <div
                key={f.src}
                className={cn(
                  'rev-foto relative overflow-hidden bg-tinta',
                  i === 0 && 'col-span-2 aspect-[4/3] xl:col-span-5 xl:aspect-[4/5]',
                  i === 1 && 'aspect-[4/5] xl:col-span-4 xl:mt-24',
                  i === 2 && 'aspect-[4/5] xl:col-span-3 xl:mt-48',
                )}
              >
                <Image
                  src={f.src}
                  alt={f.alt}
                  fill
                  sizes={i === 0 ? '(min-width: 1280px) 40vw, 100vw' : '(min-width: 1280px) 30vw, 50vw'}
                  className={cn('object-cover', i === 0 && 'object-[50%_62%] xl:object-center')}
                />
              </div>
            ))}
          </div>
          <p className="rev texto-cuerpo max-w-[60ch]">{flota.pie}</p>
        </div>

        <figure className="rev m-0 flex flex-col gap-8 bg-tinta p-6 text-hero-ink sm:p-8 xl:col-span-12 xl:flex-row xl:items-end xl:justify-between xl:gap-12 xl:p-12">
          <div className="flex max-w-[44ch] flex-col gap-6">
            <blockquote className="m-0 text-2xl font-semibold leading-snug text-balance xl:text-3xl">{`“${cita.texto}”`}</blockquote>
            <figcaption className="texto-cuerpo font-semibold">{cita.atribucion}</figcaption>
          </div>
          <Link href={`#${ANCLA_DE.reservar}`} className={botonClases({ variante: 'campana-claro' })}>
            {reservar}
          </Link>
        </figure>
      </div>
    </section>
  );
}
