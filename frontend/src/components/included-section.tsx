import { Boat, Check, Clock, Plus, Snowflake, SteeringWheel } from '@phosphor-icons/react/ssr';
import type { ComponentType } from 'react';
import type { IconProps } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type IncludedSectionProps = {
  included: Dictionary['included'];
};

/**
 * El icono no puede vivir en el JSON, asi que el diccionario manda una clave y
 * aqui se traduce a componente. Si alguien agrega una linea con una clave que
 * no existe, cae en el check en vez de romper la pagina.
 */
const ICONOS: Record<string, ComponentType<IconProps>> = {
  panga: Boat,
  capitan: SteeringWheel,
  hielera: Snowflake,
  horas: Clock,
};

/**
 * Que trae el viaje, en tres bloques con tres **pesos visuales distintos**.
 *
 * La version anterior eran tres listas de texto seguidas: se leian como la
 * misma cosa dicha tres veces y la seccion entera quedaba plana. Aqui cada
 * bloque se ve como lo que es:
 *
 *   - **Va incluido** son tarjetas en grid 2x2 con icono grande y fondo
 *     `surface`. Es lo que el cliente compra, y es lo unico de esta seccion
 *     que justifica el precio: tiene que pesar mas que el resto. El borde
 *     izquierdo de acento en cada tarjeta le da ritmo sin decoracion gratuita.
 *   - **Lo que llevas tu** es un checklist en dos columnas. Se lee como lo
 *     que es: una maleta que hay que hacer.
 *   - **Lo que nos puedes pedir** son cards horizontales compactas sobre
 *     fondo `surface`, visualmente distintas de las tarjetas de arriba (son
 *     mas ligeras, el `+` es prominente). El fondo tintado las separa del
 *     checklist sin necesidad de un divisor.
 *
 * Es Server Component: aqui no hay nada interactivo.
 */
export function IncludedSection({ included }: IncludedSectionProps) {
  return (
    <section id="incluye" className="scroll-mt-24 bg-surface py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        {/* ---------- Header ---------- */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-16">
          <div>
            <span aria-hidden className="rev-regla mb-6 block h-[3px] w-12 bg-action" />
            <h2 className="max-w-[14ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]">
              {included.headline}
            </h2>
          </div>
          <p className="max-w-[46ch] text-lg leading-relaxed text-muted lg:pb-2">
            {included.intro}
          </p>
        </div>

        {/* ---------- Incluido: grid 2x2 con peso visual fuerte ----------
            Cada tarjeta tiene un borde izquierdo de acento, icono grande y mas
            aire interior. El grid es 2x2 en desktop y 1 columna en movil. El
            fondo `background` (paper) contrasta contra `surface` (mist) de la
            seccion, y el borde izquierdo le da ritmo sin caer en decoracion. */}
        <div className="rev mt-12 grid gap-4 sm:grid-cols-2 lg:gap-5">
          {included.included.map((item) => {
            const Icono = ICONOS[item.icon] ?? Check;
            return (
              <div
                key={item.title}
                className="flex gap-5 border-l-[3px] border-accent bg-background p-6 lg:p-8"
              >
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-surface-deep">
                  <Icono size={24} weight="light" className="text-accent" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-lg leading-snug text-foreground">{item.title}</span>
                  <span className="text-sm leading-relaxed text-muted">{item.body}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* ---------- Lo que llevas tu: checklist 2 columnas ----------
            Presentacion de lista de verificacion en dos columnas en desktop,
            con checks limpios. El divisor superior y el espacio lo separan
            visualmente del bloque de arriba sin necesidad de fondo distinto. */}
        <div className="rev mt-16 border-t border-border-strong pt-10 lg:mt-20 lg:pt-12">
          <h3 className="text-lg text-foreground">{included.bringTitle}</h3>
          <ul className="mt-6 grid gap-x-10 gap-y-3 sm:grid-cols-2">
            {included.bring.map((item) => (
              <li key={item} className="flex items-start gap-3 text-base leading-snug">
                <span
                  aria-hidden
                  className="mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center border border-border-strong"
                >
                  <Check size={11} weight="bold" className="text-accent" />
                </span>
                <span className="text-foreground">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* ---------- Extras: cards horizontales sobre fondo tintado ----------
            Visualmente distintas de las tarjetas "incluido" de arriba: son mas
            compactas, sin borde de acento, con fondo `background` (paper) y el
            `+` prominente. El bloque completo va sobre `surface` asi que las
            cards contrastan sin esfuerzo. */}
        <div className="rev mt-14 lg:mt-16">
          <h3 className="text-lg text-foreground">{included.addonsTitle}</h3>
          <p className="mt-2 max-w-[56ch] text-sm leading-relaxed text-muted">
            {included.addonsIntro}
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {included.addons.map((addon) => (
              <div
                key={addon.title}
                className="flex items-start gap-4 bg-background px-5 py-4"
              >
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-deep">
                  <Plus size={13} weight="bold" className="text-accent" />
                </span>
                <span className="flex flex-col gap-0.5">
                  <span className="text-base leading-snug text-foreground">{addon.title}</span>
                  <span className="text-sm leading-relaxed text-muted">{addon.body}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
