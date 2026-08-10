import type { ReactNode } from 'react';

type CheckoutSectionCardProps = {
  step: number;
  title: string;
  children: ReactNode;
};

export function CheckoutSectionCard({ step, title, children }: CheckoutSectionCardProps) {
  return (
    <section className="rounded-3xl border border-border bg-surface p-6 sm:p-8">
      <div className="flex items-center gap-3">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-medium text-accent-foreground">
          {step}
        </span>
        <h2 className="text-sm font-medium tracking-tight text-foreground">{title}</h2>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}
