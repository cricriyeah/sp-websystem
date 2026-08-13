import { Users } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { MediaPlaceholder } from '@/components/media-placeholder';

type FleetSectionProps = {
  fleet: Dictionary['fleet'];
};

/**
 * Las pangas. En pesca deportiva el cliente compra el bote tanto como el viaje,
 * y hasta ahora la flota solo existia en el backoffice.
 */
export function FleetSection({ fleet }: FleetSectionProps) {
  return (
    <section id="flota" className="scroll-mt-20 bg-surface py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {fleet.headline}
        </h2>
        <p className="mt-5 max-w-[60ch] text-base leading-relaxed text-muted">{fleet.intro}</p>

        <div className="mt-12 grid gap-8 sm:grid-cols-2">
          {fleet.boats.map((boat) => (
            <article key={boat.name} className="flex flex-col">
              <MediaPlaceholder hint={boat.photoHint} aspect="video" />

              <h3 className="mt-5 text-xl font-medium tracking-tight text-foreground">
                {boat.name}
              </h3>
              <p className="mt-1 flex items-center gap-2 text-sm text-muted">
                <Users size={16} className="shrink-0 text-accent" />
                {boat.capacity}
              </p>

              <p className="mt-5 text-xs tracking-wide text-muted uppercase">{fleet.specsLabel}</p>
              <ul className="mt-2 flex flex-col gap-1.5 text-sm text-foreground">
                {boat.specs.map((spec) => (
                  <li key={spec} className="flex gap-2">
                    <span className="text-accent">·</span>
                    {spec}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <p className="mt-10 text-sm text-muted">{fleet.note}</p>
      </div>
    </section>
  );
}
