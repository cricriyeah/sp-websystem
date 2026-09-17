// frontend/src/components/sede-hero.tsx
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada, SedeHeroContenido } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { SelectorExperiencia } from '@/components/selector-experiencia';
import { BookingBar } from '@/components/booking-bar';
import { ID_BARRA_PORTADA } from '@/components/sticky-booking-bar';

type SedeHeroProps = {
  lang: Locale;
  sedeSlug: string;
  contenido: SedeHeroContenido;
  mostrarBookingBar: boolean;
  destacadas: SedeDestacada[];
  paquetes: PaqueteCatalogo[];
  servicios: ServicioCatalogo[];
  moneda: Moneda;
  booking: Dictionary['booking'];
  minDate: string;
  verTodoLabel: string;
  hrefVerTodo: string;
};

/**
 * Hero de la pagina de sede. A diferencia de `Hero.tsx` (que sigue siendo el
 * de la portada de hoy, sin caller tras la Tarea 9), este:
 * - Acepta imagen fija ademas de video (Los Cabos no tiene video).
 * - `facts` puede venir vacio (Los Cabos) — no renderiza la fila si esta vacia.
 * - Solo monta `BookingBar` (con `ID_BARRA_PORTADA`) cuando `mostrarBookingBar`
 *   es true — hoy, unicamente para `sedeSlug === 'la-paz'` (spec §6.1, §7).
 * - Siempre monta `SelectorExperiencia` (Paso 0), en todas las sedes.
 */
export function SedeHero({
  lang,
  sedeSlug,
  contenido,
  mostrarBookingBar,
  destacadas,
  paquetes,
  servicios,
  moneda,
  booking,
  minDate,
  verTodoLabel,
  hrefVerTodo,
}: SedeHeroProps) {
  return (
    <section className="relative z-10 bg-background">
      <div className="relative w-full overflow-hidden">
        {contenido.video ? (
          <video
            autoPlay
            muted
            loop
            playsInline
            poster={contenido.imagen ?? undefined}
            className="absolute inset-0 h-full w-full object-cover"
          >
            <source src={contenido.video} type="video/webm" />
          </video>
        ) : contenido.imagen ? (
          // eslint-disable-next-line @next/next/no-img-element -- fondo a sangre, mismo tratamiento que el poster del video de la-paz
          <img src={contenido.imagen} alt="" className="absolute inset-0 h-full w-full object-cover" />
        ) : null}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, rgba(10,11,14,0.88) 0%, rgba(10,11,14,0.42) 44%, rgba(10,11,14,0.10) 100%)',
          }}
        />

        <div className="relative flex min-h-[calc(52svh_+_var(--nav-alto))] flex-col justify-end lg:min-h-[calc(min(56svh,520px)_+_var(--nav-alto))]">
          <div className="mx-auto w-full max-w-6xl px-6 pt-[calc(5rem_+_var(--nav-alto))] pb-10 sm:px-8 lg:px-12 lg:pt-[calc(7rem_+_var(--nav-alto))] lg:pb-16">
            <h1 className="titulo-entra max-w-[19ch] text-[38px] leading-[1.02] text-hero-ink sm:text-6xl lg:text-[76px] lg:leading-[0.98]">
              {contenido.titulo.start} <span className="acento">{contenido.titulo.emphasis}</span>{' '}
              {contenido.titulo.end}
            </h1>
            <p className="titulo-entra titulo-entra-tarde mt-5 max-w-[52ch] text-base leading-relaxed text-hero-ink-soft lg:mt-6 lg:text-lg">
              {contenido.subtitulo}
            </p>

            <SelectorExperiencia
              lang={lang}
              sedeSlug={sedeSlug}
              destacadas={destacadas}
              paquetes={paquetes}
              servicios={servicios}
              moneda={moneda}
              booking={booking}
              minDate={minDate}
              verTodoLabel={verTodoLabel}
              hrefVerTodo={hrefVerTodo}
            />
          </div>
        </div>
      </div>

      {mostrarBookingBar && (
        <div
          id={ID_BARRA_PORTADA}
          className="relative mx-auto -mt-8 max-w-6xl px-6 sm:px-8 lg:-mt-12 lg:max-w-4xl lg:px-12"
        >
          <BookingBar lang={lang} booking={booking} minDate={minDate} />
        </div>
      )}

      {contenido.facts.length > 0 && (
        <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-8 px-6 pt-12 pb-16 sm:px-8 lg:grid-cols-4 lg:gap-x-0 lg:px-12 lg:pt-14 lg:pb-20">
          {contenido.facts.map(({ value, label }, i) => (
            <div
              key={label}
              className={`flex flex-col gap-1 lg:px-8 ${
                i === 0 ? 'lg:pl-0' : 'lg:border-l lg:border-border'
              } ${i === contenido.facts.length - 1 ? 'lg:pr-0' : ''}`}
            >
              <dt className="text-xl font-bold tracking-[-0.02em] text-accent lg:text-[23px]">{value}</dt>
              <dd className="text-sm text-muted">{label}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
