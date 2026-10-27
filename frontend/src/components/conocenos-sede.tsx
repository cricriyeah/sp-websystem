import Image from 'next/image';
import type { SedeConocenos } from '@/content/sedes-tipos';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

type Props = {
  id: string;
  conocenos: SedeConocenos;
  fondo: Fondo;
};

/**
 * «Conócenos»: quién lleva el negocio, en cinco bloques (la foto, el título con su apertura, los dos socios y una
 * cita con su fuente) para que se lea de un vistazo. En escritorio la foto única ocupa la columna izquierda,
 * entera, y el texto la derecha; en el teléfono todo se apila: título, foto, apertura, socios y cita. Sin
 * botones: la decisión de reservar la sigue llevando la sección de los viajes. El contenido es de `sedes-cuerpo`:
 * solo La Paz lo tiene hoy y sin él la sección no se pinta (`seccionesDeSede`).
 *
 * Server Component.
 */
export function ConocenosSede({ id, conocenos, fondo }: Props) {
  const { titulo, apertura, foto, socios, cita } = conocenos;
  // El paso de tono: el panel de la cita es gris sobre blanco y blanco sobre gris.
  const panel = fondo === 'cafe-bruma' ? 'bg-superficie' : 'bg-cafe-bruma';
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto grid max-w-[1440px] gap-x-16 gap-y-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-x-20 lg:px-12">
        <h2 id={`${id}-titulo`} className="rev max-w-[18ch] texto-seccion text-balance lg:col-start-2 lg:row-start-1 lg:self-end">{titulo}</h2>

        <div className="rev-foto relative aspect-[4/5] overflow-hidden bg-tinta lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:aspect-auto lg:min-h-[34rem]">
          <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1024px) 42vw, 100vw" className="object-cover object-top" />
        </div>

        <div className="flex flex-col gap-10 lg:col-start-2 lg:row-start-2">
          <p className="rev max-w-[40ch] text-xl leading-snug">{apertura}</p>

          <ul className="grid gap-8 sm:grid-cols-2 sm:gap-10">
            {socios.map((socio) => (
              <li key={socio.nombre} className="rev">
                <strong className="block text-lg font-semibold leading-snug">{socio.nombre}</strong>
                <span className="mt-2 block texto-cuerpo">{socio.texto}</span>
              </li>
            ))}
          </ul>

          <figure className={cn('rev m-0 p-6 sm:p-8', panel)}>
            <blockquote className="m-0 text-xl font-semibold leading-snug text-balance">{`“${cita.texto}”`}</blockquote>
            <figcaption className="mt-4 texto-pequeno">{cita.atribucion}</figcaption>
          </figure>
        </div>
      </div>
    </section>
  );
}
