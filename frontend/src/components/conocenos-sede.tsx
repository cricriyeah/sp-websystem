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
 * «Conócenos»: quién lleva el negocio. Sigue el mosaico «foto ancha + campo de color» de la dirección de taste
 * («Photographs at uneven sizes», sección `about`), con la proporción nativa de la foto (2:1, no se recorta: se ven el
 * capitán y el nombre de la panga).
 *
 * De arriba abajo: el título en tres líneas, con la del medio («generaciones») un tamaño por encima y en el acento;
 * la apertura como frase guía bajo el título (columnas 1-6); el mosaico, con la foto en las columnas 1-8 y, de su
 * misma altura, un campo de color tinta en las 9-12 que lleva la cita de prensa (la prueba externa pegada a la foto);
 * y los dos socios en dos columnas de seis. Por debajo de 1280 px (donde la foto y el campo no caben lado a lado) todo
 * se apila en ese mismo orden. Sin botones: la decisión de reservar la sigue llevando la sección de los viajes.
 * El contenido es de `sedes-cuerpo`: solo La Paz lo tiene hoy y sin él la sección no se pinta (`seccionesDeSede`).
 *
 * Server Component.
 */
export function ConocenosSede({ id, conocenos, fondo }: Props) {
  const { titulo, apertura, foto, socios, cita } = conocenos;
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

        <figure className="rev m-0 flex flex-col justify-center gap-6 bg-tinta p-6 text-hero-ink sm:p-8 xl:col-span-4">
          <blockquote className="m-0 text-2xl font-semibold leading-snug text-balance xl:text-3xl">{`“${cita.texto}”`}</blockquote>
          <figcaption className="texto-cuerpo font-semibold">{cita.atribucion}</figcaption>
        </figure>

        <ul className="grid gap-8 sm:grid-cols-2 sm:gap-6 xl:col-span-12">
          {socios.map((socio) => (
            <li key={socio.nombre} className="rev">
              <strong className="block text-xl font-semibold leading-snug">{socio.nombre}</strong>
              <span className="mt-3 block max-w-[60ch] texto-cuerpo">{socio.texto}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
