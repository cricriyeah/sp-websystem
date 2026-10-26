import Image from 'next/image';
import type { SedeDia } from '@/content/sedes-tipos';
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

type Props = {
  id: string;
  dia: SedeDia;
  textos: { anterior: string; siguiente: string };
  fondo: Fondo;
};

/**
 * «Tu día de pesca» (F10): los momentos del viaje, uno tras otro, como una fila que se arrastra. Cada uno es
 * una foto con su palabra gigante (la hora, «A bordo», «Pesca», «Regresa») y una frase. Las fotos son
 * decorativas: la palabra y la frase lo dicen todo. El contenido es de `sedes-cuerpo`: solo La Paz lo tiene hoy
 * y sin él la sección no se pinta (`seccionesDeSede`).
 *
 * Server Component (la fila es una isla cliente).
 */
export function DiaDeSede({ id, dia, textos, fondo }: Props) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <FilaArrastrable
        cabeza={<h2 id={`${id}-titulo`} className="rev texto-seccion">{dia.titulo}</h2>}
        etiqueta={dia.etiqueta}
        textos={textos}
      >
        {dia.momentos.map((momento, i) => (
          <figure
            key={momento.titulo}
            className="group rev relative m-0 aspect-[3/4] flex-[0_0_78vw] snap-start overflow-hidden bg-tinta text-hero-ink sm:flex-[0_0_clamp(17.5rem,30vw,28.75rem)]"
          >
            <Image
              src={momento.foto}
              alt=""
              fill
              // La tarjeta es vertical (3:4) y las fotos horizontales: `object-cover` las escala a la ALTURA de la tarjeta,
              // así que la foto ocupa unas 2,4 veces el ancho de la tarjeta. Con `sizes` igual al ancho de la tarjeta,
              // Next sirve una versión chica que el navegador estira (borrosa).
              sizes="(min-width: 640px) 72vw, 185vw"
              loading={i === 0 ? 'eager' : 'lazy'}
              className="object-cover transition-transform duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.04]"
            />
            <div aria-hidden="true" className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />
            <figcaption className="absolute inset-x-0 bottom-0 flex flex-col gap-3 p-5 sm:p-6">
              <strong className="texto-grande text-balance">{momento.titulo}</strong>
              <span className="max-w-[34ch] texto-cuerpo leading-snug">{momento.texto}</span>
            </figcaption>
          </figure>
        ))}
      </FilaArrastrable>
    </section>
  );
}
