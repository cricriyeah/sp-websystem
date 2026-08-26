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
 * Que trae el viaje, en tres bloques con **tres pesos visuales distintos**.
 *
 * La version anterior eran tres listas de texto seguidas: se leian como la
 * misma cosa dicha tres veces y la seccion entera quedaba plana. Aqui cada
 * bloque se ve como lo que es:
 *
 *   - **Va incluido** son tarjetas con icono. Es lo que el cliente compra, y
 *     es lo unico de esta seccion que justifica el precio: tiene que pesar mas
 *     que el resto.
 *   - **Lo que llevas tu** es una lista de verificacion, con su casilla. Se lee
 *     como lo que es —una maleta que hay que hacer— y no como una carencia.
 *   - **Lo que nos puedes pedir** son extras marcados con un `+`. El signo hace
 *     el trabajo que antes hacia la equis, pero en positivo: esto se suma, no
 *     te falta.
 *
 * **No hay lista de "no incluido"** y no es un olvido. Antes eran dos columnas
 * enfrentadas, una de checks y otra de equis, y la de equis era lo primero que
 * saltaba a la vista: cuatro renglones seguidos diciendo que no. Nada de lo que
 * habia ahi se perdio, solo cambio de lugar y de tono.
 *
 * Es Server Component: aqui no hay nada interactivo.
 */
export function IncludedSection({ included }: IncludedSectionProps) {
  return (
    <section id="incluye" className="scroll-mt-20 bg-surface py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
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

        {/* Las tarjetas van sobre `bg-background` y la seccion sobre `bg-surface`:
            el contraste las levanta sin necesidad de sombra ni de color. */}
        <div className="mt-12 grid gap-px border border-border-strong bg-border-strong sm:grid-cols-2 lg:grid-cols-4">
          {included.included.map((item) => {
            const Icono = ICONOS[item.icon] ?? Check;
            return (
              <div key={item.title} className="flex flex-col gap-3 bg-background p-7 lg:p-8">
                <Icono size={26} weight="light" className="text-accent" />
                <span className="text-lg leading-snug text-foreground">{item.title}</span>
                <span className="text-sm leading-relaxed text-muted">{item.body}</span>
              </div>
            );
          })}
        </div>

        <div className="mt-16 grid gap-12 lg:grid-cols-[1.15fr_1fr] lg:gap-20">
          <div>
            <h3 className="text-lg text-foreground">{included.bringTitle}</h3>
            <ul className="mt-5 flex flex-col gap-3">
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

          <div className="border-t border-border-strong pt-8 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-20">
            <h3 className="text-lg text-foreground">{included.addonsTitle}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">{included.addonsIntro}</p>
            <ul className="mt-5 flex flex-col">
              {included.addons.map((addon) => (
                <li
                  key={addon.title}
                  className="flex items-start gap-3 border-b border-border py-4 last:border-b-0"
                >
                  <Plus size={14} weight="bold" className="mt-1.5 shrink-0 text-accent" />
                  <span className="flex flex-col gap-1">
                    <span className="text-base leading-snug text-foreground">{addon.title}</span>
                    <span className="text-sm leading-relaxed text-muted">{addon.body}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
