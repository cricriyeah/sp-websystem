import { Check } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type CheckoutStepperProps = {
  stepper: Dictionary['checkout']['stepper'];
  /** 1-4. Cual paso esta activo ahora mismo. */
  actual: number;
};

const TOTAL_PASOS = 4;

/**
 * Responde "cuanto me falta" en el primer cuadro, sin tener que hacer scroll
 * para averiguarlo. Reemplaza a los circulos numerados que traia cada
 * `CheckoutSectionCard` — las dos cosas diciendo lo mismo (progreso) sumaban
 * ruido, no claridad.
 *
 * Version de escritorio: los 4 pasos a la vista, con la linea entre ellos
 * rellenandose segun avanza. Version de movil: puntos + una sola etiqueta,
 * fija justo debajo del `SiteHeader` (`--nav-alto`, ver globals.css) porque
 * sin ella fuera de cuadro el cliente pierde la unica senal de "cuanto falta"
 * que tiene.
 */
export function CheckoutStepper({ stepper, actual }: CheckoutStepperProps) {
  const pasos = [stepper.trip, stepper.contact, stepper.extras, stepper.payment];

  return (
    <>
      {/* --- Movil: compacta y fija. --------------------------------------- */}
      <div className="sticky top-[var(--nav-alto)] z-30 border-b border-border bg-surface/95 px-6 py-3 backdrop-blur-sm sm:px-8 lg:hidden">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <div className="flex shrink-0 items-center gap-1.5" aria-hidden>
            {pasos.map((_, i) => {
              const numero = i + 1;
              return (
                <span
                  key={numero}
                  className={`h-1.5 w-1.5 rounded-full transition-colors ${
                    numero <= actual ? 'bg-accent' : 'bg-border-strong'
                  }`}
                />
              );
            })}
          </div>
          <p className="text-xs font-medium text-muted">
            {stepper.stepOf
              .replace('{current}', String(actual))
              .replace('{total}', String(TOTAL_PASOS))}{' '}
            <span className="text-foreground">· {pasos[actual - 1]}</span>
          </p>
        </div>
      </div>

      {/* --- Escritorio: los 4 pasos a la vista. ---------------------------- */}
      <div className="mx-auto hidden max-w-6xl px-6 pt-6 sm:px-8 lg:block lg:px-12">
        <ol className="flex items-center">
          {pasos.map((label, i) => {
            const numero = i + 1;
            const completado = numero < actual;
            const activo = numero === actual;

            return (
              <li key={label} className="flex flex-1 items-center last:flex-none">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-colors ${
                      completado
                        ? 'bg-accent text-accent-foreground'
                        : activo
                          ? 'border-2 border-accent text-accent'
                          : 'border border-border-strong text-muted'
                    }`}
                  >
                    {completado ? <Check size={12} weight="bold" /> : numero}
                  </span>
                  <span
                    className={`text-sm ${
                      activo ? 'font-medium text-foreground' : completado ? 'text-foreground' : 'text-muted'
                    }`}
                  >
                    {label}
                  </span>
                </div>

                {numero < TOTAL_PASOS && (
                  <span
                    aria-hidden
                    className={`mx-4 h-px flex-1 transition-colors ${
                      completado ? 'bg-accent' : 'bg-border'
                    }`}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </>
  );
}
