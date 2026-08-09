import { Clock, SunHorizon, UsersThree, CalendarCheck } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type AboutSectionProps = {
  about: Dictionary['about'];
};

export function AboutSection({ about }: AboutSectionProps) {
  const facts = [
    { icon: Clock, ...about.facts.duration },
    { icon: SunHorizon, ...about.facts.departure },
    { icon: UsersThree, ...about.facts.capacity },
    { icon: CalendarCheck, ...about.facts.season },
  ];

  return (
    <section id="nosotros" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto grid max-w-6xl gap-14 px-6 sm:px-8 lg:grid-cols-12 lg:gap-20 lg:px-12">
        <div className="lg:col-span-5">
          <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
            {about.headline}
          </h2>
          <p className="mt-6 max-w-[60ch] text-base leading-relaxed text-muted">{about.body1}</p>
          <p className="mt-4 max-w-[60ch] text-base leading-relaxed text-muted">{about.body2}</p>
        </div>

        <dl className="grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:col-span-7">
          {facts.map(({ icon: Icon, value, label }) => (
            <div key={label} className="border-t border-border pt-5">
              <Icon size={24} className="text-accent" />
              <dt className="mt-4 text-xl font-medium tracking-tight text-foreground">{value}</dt>
              <dd className="mt-1 text-sm text-muted">{label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
