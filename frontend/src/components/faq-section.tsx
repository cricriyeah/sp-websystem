import { CaretDown } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type FaqSectionProps = {
  faq: Dictionary['faq'];
};

export function FaqSection({ faq }: FaqSectionProps) {
  return (
    <section id="preguntas" className="scroll-mt-20 bg-surface py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {faq.headline}
        </h2>

        <div className="mt-12 max-w-3xl divide-y divide-border border-y border-border">
          {faq.items.map((item) => (
            <details key={item.q} className="group py-2">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-4 text-left text-base font-medium text-foreground [&::-webkit-details-marker]:hidden">
                {item.q}
                <CaretDown
                  size={18}
                  className="shrink-0 text-muted transition-transform duration-200 group-open:rotate-180"
                />
              </summary>
              <p className="max-w-[65ch] pr-10 pb-5 text-base leading-relaxed text-muted">
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
