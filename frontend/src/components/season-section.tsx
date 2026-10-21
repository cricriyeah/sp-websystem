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
};

/**
 * Calendario de especies (F10): una intro y el selector de temporada con su foto. Los datos son de `sedes-cuerpo`: solo La Paz tiene hoy, y sin ellos la
 * sección no se pinta (`seccionesDeSede`).
 *
 * Server Component (el selector es una isla cliente).
 */
export function SeasonSection({ id, titulo, temporadas, textos, fondo }: SeasonSectionProps) {
  return (
    <SectionShell id={id} fondo={fondo} titulo={titulo}>
      <p className="mt-4 max-w-[60ch] text-lg leading-relaxed">{temporadas.intro}</p>
      <TemporadasSelector temporadas={temporadas} textos={textos} />
    </SectionShell>
  );
}
