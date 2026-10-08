import { Check } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { CifraAnimada } from '@/components/checkout/cifra-animada';

type CheckoutStepperProps = {
  stepper: Dictionary['checkout']['stepper'];
  /** 1-N. Cual paso esta activo ahora mismo. */
  actual: number;
  /** Pasos personalizados. Si no se especifican, se usan los 4 por omisión. */
  steps?: string[];
  /** Cifra que acompaña al progreso (total del pedido, o lo que se paga en este paso). */
  totalMovil?: string;
  /** Rótulo sobre la cifra cuando no es el total ("Pagas ahora"). */
  rotulo?: string;
  /** Total del pedido, junto a la cifra de este paso cuando son distintas (solo escritorio). */
  totalGeneral?: string;
  /** Etiquetas de escritorio: más cortas que `steps` ("Pago 1" en vez de "Pago 1 · Empresa"). */
  etiquetasCortas?: string[];
};

/**
 * Responde "cuanto me falta" en el primer cuadro, sin tener que hacer scroll
 * para averiguarlo. Reemplaza a los circulos numerados que traia cada
 * `CheckoutSectionCard` — las dos cosas diciendo lo mismo (progreso) sumaban
 * ruido, no claridad.
 *
 * Version de escritorio: los pasos a la vista, con la linea entre ellos
 * rellenandose segun avanza. Version de movil: puntos + una sola etiqueta,
 * fija justo debajo del `SiteHeader` (`--nav-alto`, ver globals.css) porque
 * sin ella fuera de cuadro el cliente pierde la unica senal de "cuanto falta"
 * que tiene.
 */
export function CheckoutStepper({ stepper, actual, steps, totalMovil, rotulo, totalGeneral, etiquetasCortas }: CheckoutStepperProps) {
  const pasos = steps ?? [stepper.trip, stepper.contact, stepper.extras, stepper.payment];
  const totalPasos = pasos.length;
  const etiquetas = etiquetasCortas ?? pasos;

  return (
    <>
      {/* --- Movil: compacta y fija. --------------------------------------- */}
      <div className="sticky top-[var(--nav-alto)] z-30 border-b border-border bg-surface px-6 py-3 sm:px-8 lg:hidden">
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
          <p className={totalMovil ? "min-w-0 flex-1 truncate text-xs font-medium text-muted" : "text-xs font-medium text-muted"}>
            {stepper.stepOf
              .replace('{current}', String(actual))
              .replace('{total}', String(totalPasos))}{' '}
            <span className="text-foreground">· {pasos[actual - 1]}</span>
          </p>
          {totalMovil && (
            <CifraAnimada valor={`${rotulo ?? ''}|${totalMovil}`} className="flex shrink-0 flex-col items-end leading-tight">
              {rotulo && <span className="text-[10px] font-normal text-muted">{rotulo}</span>}
              <span className="text-xs font-semibold text-foreground">{totalMovil}</span>
            </CifraAnimada>
          )}
        </div>
      </div>

      {/* --- Escritorio: los 4 pasos a la vista. ---------------------------- */}
      {/* Fija bajo el header, como la de móvil: el progreso es información que
          debe seguir a la vista mientras el cliente baja por las tarjetas. */}
      <div className="hidden border-b border-border bg-surface lg:sticky lg:top-[var(--nav-alto)] lg:z-30 lg:block">
        <div className="mx-auto max-w-6xl px-6 pt-4 pb-3 sm:px-8 lg:px-12">
        <div className="flex items-center gap-8">
        <ol className="flex min-w-0 flex-1 items-center" aria-label={stepper.stepOf.replace('{current}', String(actual)).replace('{total}', String(totalPasos))}>
          {etiquetas.map((label, i) => {
            const numero = i + 1;
            const completado = numero < actual;
            const activo = numero === actual;

            return (
              <li key={label} aria-current={activo ? 'step' : undefined} className="flex flex-1 items-center last:flex-none">
                <div className="flex min-w-0 items-center gap-2.5">
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

                {numero < totalPasos && (
                  <span
                    aria-hidden
                    className={`mx-4 h-px min-w-6 flex-1 transition-colors ${
                      completado ? 'bg-accent' : 'bg-border'
                    }`}
                  />
                )}
              </li>
            );
          })}
        </ol>
        {totalMovil && (
          <CifraAnimada valor={`${rotulo ?? ''}|${totalMovil}|${totalGeneral ?? ''}`} className="block shrink-0 text-right text-sm leading-tight">
            {rotulo && totalGeneral ? (
              <>
                <span className="text-muted">{rotulo} </span>
                <span className="font-semibold text-foreground">{totalMovil}</span>
                <span className="text-muted"> · {stepper.totalLabel} {totalGeneral}</span>
              </>
            ) : (
              <>
                <span className="text-muted">{rotulo ?? stepper.totalLabel} </span>
                <span className="font-semibold text-foreground">{totalMovil}</span>
              </>
            )}
          </CifraAnimada>
        )}
        </div>
        </div>
      </div>
    </>
  );
}
