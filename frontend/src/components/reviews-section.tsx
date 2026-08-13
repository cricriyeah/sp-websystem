import { Quotes } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappInline } from '@/components/whatsapp-inline';

type ReviewsSectionProps = {
  nav: Dictionary['nav'];
  reviews: Dictionary['reviews'];
};

const HUECOS = 3;

/**
 * Reseñas de clientes.
 *
 * Los huecos van vacios A PROPOSITO. Poner citas inventadas con nombres
 * inventados seria fabricar prueba social, y en un negocio que se vende por
 * cercania y confianza es justo lo que no se debe hacer. Cuando lleguen las
 * reseñas reales (Google, TripAdvisor, WhatsApp) se pegan tal cual aqui.
 */
export function ReviewsSection({ nav, reviews }: ReviewsSectionProps) {
  return (
    <section id="resenas" className="scroll-mt-20 bg-surface py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {reviews.headline}
        </h2>
        <p className="mt-5 max-w-[60ch] text-base leading-relaxed text-muted">{reviews.intro}</p>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: HUECOS }, (_, i) => (
            <article
              key={i}
              className="flex min-h-44 flex-col justify-between rounded-2xl border border-dashed border-border p-6"
            >
              <Quotes size={20} weight="fill" className="text-muted/40" />
              <p className="mt-4 text-sm leading-relaxed text-muted">{reviews.placeholder}</p>
              <p className="mt-4 text-xs text-muted/70">— {reviews.placeholderAuthor}</p>
            </article>
          ))}
        </div>

        <p className="mt-10 max-w-[60ch] text-sm leading-relaxed text-muted">{reviews.note}</p>
        <WhatsappInline nav={nav} label={reviews.cta} className="mt-5" />
      </div>
    </section>
  );
}
