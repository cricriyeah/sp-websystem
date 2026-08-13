import type { ReactNode } from 'react';

type CheckoutSectionCardProps = {
  step: number;
  title: string;
  /**
   * `flat` (pasos): tarjeta blanca al ras. `elevated` (resumen de pago): la
   * misma tarjeta pero con sombra marcada y el numero en color de acento, para
   * que la columna del dinero se lea como una pieza aparte y no como un paso
   * mas de la lista.
   */
  variant?: 'flat' | 'elevated';
  children: ReactNode;
};

const ESTILOS = {
  flat: 'border-border bg-surface',
  elevated: 'border-border bg-surface shadow-[0_18px_45px_rgba(11,36,32,0.16)]',
};

export function CheckoutSectionCard({
  step,
  title,
  variant = 'flat',
  children,
}: CheckoutSectionCardProps) {
  return (
    <section className={`rounded-3xl border p-6 sm:p-8 ${ESTILOS[variant]}`}>
      <div className="flex items-center gap-3">
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
            variant === 'elevated'
              ? 'bg-accent text-accent-foreground'
              : 'border border-border bg-surface text-muted'
          }`}
        >
          {step}
        </span>
        <h2 className="text-sm font-medium tracking-tight text-foreground">{title}</h2>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}
