import { Star } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappInline } from '@/components/whatsapp-inline';

type ReviewsSectionProps = {
  nav: Dictionary['nav'];
  reviews: Dictionary['reviews'];
};

const HUECOS = 2;

/**
 * Bloques de cita, sin tarjeta: cinco estrellas, la cita grande y el nombre
 * debajo, nada de borde ni fondo.
 *
 * Los huecos van vacios A PROPOSITO. Poner citas inventadas con nombres
 * inventados seria fabricar prueba social, y en un negocio que se vende por
 * cercania y confianza es justo lo que no se debe hacer. Cuando lleguen las
 * reseñas reales (Google, TripAdvisor, WhatsApp) se pegan tal cual aqui.
 */
export function ReviewsSection({ nav, reviews }: ReviewsSectionProps) {
  return (
    <section
      id="resenas"
      className="relative scroll-mt-20 overflow-hidden bg-background py-24 lg:py-32"
    >
      {/* Radial apagado detras de las citas, con el mismo indigo del acento:
          rompe el fondo plano sin competir con el, y se desvanece rapido en
          vez de cubrir la seccion entera como un degradado parejo. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'radial-gradient(55% 60% at 12% 8%, rgba(40,26,181,0.05), transparent 70%)',
        }}
      />
      <div className="relative mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <span aria-hidden className="rev-regla mb-6 block h-[3px] w-12 bg-action" />
        <h2 className="max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]">
          {reviews.headline}
        </h2>
        <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted">{reviews.intro}</p>

        <div className="mt-14 grid gap-12 sm:grid-cols-2 lg:gap-16">
          {Array.from({ length: HUECOS }, (_, i) => (
            <div key={i} className="flex flex-col gap-4">
              <div className="flex gap-1">
                {Array.from({ length: 5 }, (_, s) => (
                  <Star key={s} size={18} weight="fill" className="text-amber" />
                ))}
              </div>
              <p className="max-w-[36ch] text-2xl leading-snug font-medium tracking-tight text-foreground">
                {reviews.placeholder}
              </p>
              <span className="text-sm text-muted">{reviews.placeholderAuthor}</span>
            </div>
          ))}
        </div>

        {/* El divisor sigue: separa las citas del CTA de abajo, aunque el texto
            que explicaba de donde salen las resenas ya no va aqui — era una nota
            para nosotros, no para quien visita el sitio. */}
        <div className="mt-12 border-t border-border pt-6">
          <WhatsappInline nav={nav} label={reviews.cta} />
        </div>
      </div>
    </section>
  );
}
