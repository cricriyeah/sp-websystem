import type { Dictionary } from '@/app/[lang]/dictionaries';
import { ReviewsCarousel } from '@/components/reviews-carousel';
import { WhatsappInline } from '@/components/whatsapp-inline';

type ReviewsSectionProps = {
  nav: Dictionary['nav'];
  reviews: Dictionary['reviews'];
};

/**
 * Carrusel de citas, sin tarjeta: cinco estrellas, la cita grande y el nombre
 * debajo, nada de borde ni fondo.
 *
 * `reviews.items` son de ejemplo A PROPOSITO — nombres y citas inventados,
 * marcados como tal con `reviews.exampleNote` a la vista de quien visite el
 * sitio. Poner citas inventadas SIN avisar seria fabricar prueba social, y en
 * un negocio que se vende por cercania y confianza es justo lo que no se debe
 * hacer. Cuando lleguen las reseñas reales (Google, Facebook, WhatsApp),
 * `reviews.items` se reemplaza por esas y `exampleNote` se borra.
 */
export function ReviewsSection({ nav, reviews }: ReviewsSectionProps) {
  return (
    <section
      id="resenas"
      className="relative scroll-mt-24 overflow-hidden bg-background py-24 lg:py-32"
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

        {/* A la vista de quien visite el sitio, no solo en un comentario del
            codigo: nadie deberia poder confundir estas citas con reseñas
            reales de un cliente. */}
        <p className="mt-3 max-w-[60ch] text-xs text-muted italic">{reviews.exampleNote}</p>

        <div className="mt-14">
          <ReviewsCarousel resenas={reviews.items} prevLabel={reviews.prev} nextLabel={reviews.next} />
        </div>

        {/* Separa el carrusel del CTA de abajo. */}
        <div className="mt-12 border-t border-border pt-6">
          <WhatsappInline nav={nav} label={reviews.cta} />
        </div>
      </div>
    </section>
  );
}
