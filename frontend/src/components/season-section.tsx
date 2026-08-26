import type { Dictionary } from '@/app/[lang]/dictionaries';

type SeasonSectionProps = {
  season: Dictionary['season'];
};

// La temporada fuerte (el 3er bloque de los 4 que manda el diccionario, jul-sep)
// lleva la barra en ambar en vez de accent: es la unica distincion visual entre
// los cuatro periodos y coincide siempre con el orden fijo de `season.rows`.
const TEMPORADA_FUERTE = 2;

/**
 * Calendario de especies como cuatro bloques planos, sin tarjeta ni tabla: cada
 * uno es solo una barra de color, el periodo, la especie y una nota.
 */
export function SeasonSection({ season }: SeasonSectionProps) {
  return (
    <section id="temporadas" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <span aria-hidden className="rev-regla mb-6 block h-[3px] w-12 bg-action" />
        <h2 className="max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]">
          {season.headline}
        </h2>
        <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted">{season.intro}</p>

        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-8">
          {season.rows.map((row, i) => (
            <article key={row.period} className="flex flex-col gap-3.5">
              <div
                className={`h-[3px] w-full ${i === TEMPORADA_FUERTE ? 'bg-amber' : 'bg-accent'}`}
              />
              <p className="text-lg font-bold tracking-tight text-accent">{row.period}</p>
              <p className="text-base font-semibold leading-snug text-foreground">{row.species}</p>
              <p className="text-sm leading-relaxed text-muted">{row.note}</p>
            </article>
          ))}
        </div>

        <p className="mt-10 max-w-[60ch] border-t border-border pt-6 text-base leading-relaxed text-foreground">
          {season.note}
        </p>
      </div>
    </section>
  );
}
