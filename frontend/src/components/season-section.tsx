import { Fish } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type SeasonSectionProps = {
  season: Dictionary['season'];
};

/**
 * Calendario de especies. Es lo que mas preguntan antes de decidir la fecha, y
 * decir "depende de la temporada" sin aterrizarlo no le sirve a nadie.
 */
export function SeasonSection({ season }: SeasonSectionProps) {
  return (
    <section id="temporadas" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {season.headline}
        </h2>
        <p className="mt-5 max-w-[60ch] text-base leading-relaxed text-muted">{season.intro}</p>

        <div className="mt-12 grid gap-4 sm:grid-cols-2">
          {season.rows.map((row) => (
            <article
              key={row.period}
              className="rounded-2xl border border-border bg-surface p-6"
            >
              <p className="text-sm font-medium tracking-tight text-foreground">{row.period}</p>
              <p className="mt-4 flex items-start gap-2 text-base text-foreground">
                <Fish size={18} weight="fill" className="mt-1 shrink-0 text-accent" />
                {row.species}
              </p>
              <p className="mt-3 text-sm leading-relaxed text-muted">{row.note}</p>
            </article>
          ))}
        </div>

        {/* La honestidad sobre lo que el mar no garantiza es parte del trato. */}
        <p className="mt-8 max-w-[60ch] rounded-2xl border border-accent/30 bg-accent/5 px-5 py-4 text-sm leading-relaxed text-foreground">
          {season.note}
        </p>
      </div>
    </section>
  );
}
