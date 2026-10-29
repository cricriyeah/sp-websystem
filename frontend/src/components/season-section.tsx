import Image from 'next/image';
import type { SedeTemporadas } from '@/content/sedes-tipos';
import { TemporadasSelector } from '@/components/temporadas-selector';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type SeasonSectionProps = {
  id: string;
  titulo: string;
  /** El calendario sale del cuerpo de la sede, con la foto de cada temporada. */
  temporadas: SedeTemporadas;
  textos: { ahora: string };
  fondo: Fondo;
  /** El isotipo de la empresa: va en la esquina de arriba a la derecha de la sección, como sello. */
  isotipo?: string;
  /** Nombre de la empresa: el texto alternativo del isotipo. */
  empresa?: string;
};

/**
 * Calendario de especies (F10): una intro y el selector de temporada con su foto. Los datos son de `sedes-cuerpo`: solo La Paz tiene hoy, y sin ellos la
 * sección no se pinta (`seccionesDeSede`).
 *
 * Server Component (el selector es una isla cliente).
 */
export function SeasonSection({ id, titulo, temporadas, textos, fondo, isotipo, empresa }: SeasonSectionProps) {
  // El sello va arriba a la derecha: en el teléfono antes del título (order-first), en escritorio a su altura.
  const lado = isotipo ? (
    <span className="rev relative order-first block size-28 shrink-0 self-end overflow-hidden rounded-full bg-blanco sm:size-36 lg:order-none lg:self-start xl:size-44">
      <Image src={isotipo} alt={empresa ?? ''} fill sizes="(min-width: 1280px) 176px, 144px" className="object-contain p-[6%]" />
    </span>
  ) : undefined;
  return (
    <SectionShell id={id} fondo={fondo} titulo={titulo} lado={lado}>
      <p className="mt-4 max-w-[60ch] text-lg leading-relaxed">{temporadas.intro}</p>
      <TemporadasSelector temporadas={temporadas} textos={textos} />
    </SectionShell>
  );
}
