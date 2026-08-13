import { Check, IdentificationCard, Minus, Suitcase } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappInline } from '@/components/whatsapp-inline';

type IncludedSectionProps = {
  nav: Dictionary['nav'];
  included: Dictionary['included'];
};

/**
 * Transparencia sobre el precio: que va incluido, que no, y que traer.
 *
 * La licencia de pesca y el manejo de la captura viven aqui porque son los dos
 * temas que le pueden arruinar el dia a un cliente si se entera en el muelle.
 */
export function IncludedSection({ nav, included }: IncludedSectionProps) {
  const columnas = [
    { icono: Check, titulo: included.includedTitle, items: included.included, acento: true },
    { icono: Minus, titulo: included.notIncludedTitle, items: included.notIncluded, acento: false },
    { icono: Suitcase, titulo: included.bringTitle, items: included.bring, acento: false },
  ];

  return (
    <section id="incluye" className="scroll-mt-20 bg-surface py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {included.headline}
        </h2>
        <p className="mt-5 max-w-[60ch] text-base leading-relaxed text-muted">{included.intro}</p>

        <div className="mt-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-3">
          {columnas.map(({ icono: Icono, titulo, items, acento }) => (
            <div key={titulo} className="border-t border-border pt-5">
              <h3 className="flex items-center gap-2 text-sm font-medium tracking-tight text-foreground">
                <Icono size={16} className={acento ? 'text-accent' : 'text-muted'} />
                {titulo}
              </h3>
              <ul className="mt-4 flex flex-col gap-2.5 text-sm leading-relaxed text-muted">
                {items.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className={acento ? 'text-accent' : 'text-muted/60'}>·</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-accent/30 bg-accent/5 p-6">
            <h3 className="flex items-center gap-2 text-sm font-medium tracking-tight text-foreground">
              <IdentificationCard size={18} className="text-accent" />
              {included.licenseTitle}
            </h3>
            <p className="mt-3 max-w-[60ch] text-sm leading-relaxed text-foreground">
              {included.licenseBody}
            </p>
            <WhatsappInline nav={nav} label={included.licenseCta} className="mt-4" />
          </div>

          <div className="rounded-2xl border border-border p-6">
            <h3 className="text-sm font-medium tracking-tight text-foreground">
              {included.catchTitle}
            </h3>
            <p className="mt-3 max-w-[60ch] text-sm leading-relaxed text-muted">
              {included.catchBody}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
