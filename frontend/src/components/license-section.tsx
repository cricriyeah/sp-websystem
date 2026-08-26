import { IdentificationCard } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappInline } from '@/components/whatsapp-inline';

type LicenseSectionProps = {
  nav: Dictionary['nav'];
  license: Dictionary['license'];
};

/**
 * La licencia de pesca, con seccion propia.
 *
 * Estuvo como un parrafo al pie de "que incluye" y ahi se perdia. Es el unico
 * requisito que el cliente tiene que resolver **antes** de llegar al muelle y
 * el que mas dudas genera: si no se entiende, o el viaje empieza mal o la
 * reserva no se hace. Por eso va suelta, con los pasos numerados y la salida
 * por WhatsApp para quien no quiera hacer el tramite solo.
 *
 * Los pasos van numerados a mano y no como `<ol>` con marcador propio para que
 * el numero pueda tener el tamano y el color que lleva aqui; el orden sigue
 * siendo el del documento, que es lo que lee un lector de pantalla.
 */
export function LicenseSection({ nav, license }: LicenseSectionProps) {
  return (
    <section id="licencia" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <p className="flex items-center gap-2 text-sm font-medium text-accent">
          <IdentificationCard size={20} weight="fill" />
          CONAPESCA
        </p>
        <h2 className="mt-3 max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]">
          {license.headline}
        </h2>
        <p className="mt-4 max-w-[62ch] text-lg leading-relaxed text-muted">{license.intro}</p>

        <ol className="mt-12 grid gap-8 border-t border-border-strong pt-10 sm:grid-cols-3 lg:gap-12">
          {license.steps.map((step, i) => (
            <li key={step.title} className="flex flex-col gap-2">
              <span className="font-display text-3xl leading-none tracking-[var(--tracking-titulo)] text-accent">
                {i + 1}
              </span>
              <span className="text-lg text-foreground">{step.title}</span>
              <span className="max-w-[38ch] text-base leading-relaxed text-muted">{step.body}</span>
            </li>
          ))}
        </ol>

        <div className="mt-12 flex flex-col gap-3 border border-border-strong bg-surface p-8 lg:p-10">
          <h3 className="text-lg text-foreground">{license.helpTitle}</h3>
          <p className="max-w-[62ch] text-base leading-relaxed text-muted">{license.helpBody}</p>
          <WhatsappInline
            nav={nav}
            label={license.cta}
            mensaje={license.whatsappMessage}
            className="mt-3 self-start"
          />
        </div>
      </div>
    </section>
  );
}
