import type { ReactNode } from 'react';
import { Skeleton } from '@/components/skeleton';

/** Estructura compartida por las pantallas de carga de los checkouts. */
export function CheckoutLoadingShell({
  children,
  withTitle = false,
  showSummaryMobile = false,
  stepCount = 4,
}: {
  children: ReactNode;
  withTitle?: boolean;
  showSummaryMobile?: boolean;
  stepCount?: number;
}) {
  const steps = Array.from({ length: stepCount }, (_, index) => index + 1);
  return (
    <div className="min-h-dvh bg-surface">
      <div className="fixed inset-x-0 top-0 z-40 lg:top-4 lg:px-8" aria-hidden="true">
        <div className="mx-auto flex h-20 w-full max-w-[1440px] items-center justify-between border-b border-border bg-background px-6 sm:px-8 lg:border lg:px-6 lg:shadow-[0_18px_45px_rgba(11,36,32,0.16)]">
          <Skeleton className="h-11 w-32" />
          <Skeleton className="h-11 w-11" />
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
        <Skeleton className="h-4 w-24" />
      </div>

      {withTitle && (
        <div className="mx-auto max-w-6xl px-6 pt-6 sm:px-8 lg:px-12">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="mt-2 h-4 w-72 max-w-full" />
        </div>
      )}

      <div className="sticky top-[var(--nav-alto)] z-30 border-b border-border bg-surface/95 px-6 py-3 sm:px-8 lg:hidden" aria-hidden="true">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <div className="flex gap-1.5">
            {steps.map((step) => <Skeleton key={step} className="h-1.5 w-1.5 rounded-full" />)}
          </div>
          <Skeleton className="h-3 w-36" />
        </div>
      </div>

      <div className="mx-auto hidden max-w-6xl gap-4 px-6 pt-6 sm:px-8 lg:flex lg:px-12" aria-hidden="true">
        {steps.map((step) => (
          <div key={step} className="flex min-w-0 flex-1 items-center gap-2">
            <Skeleton className="h-6 w-6 shrink-0 rounded-full" />
            <Skeleton className="h-4 w-24 max-w-full" />
            {step < stepCount && <Skeleton className="h-px min-w-4 flex-1" />}
          </div>
        ))}
      </div>

      <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex min-w-0 flex-col gap-6">{children}</div>
        <section className={`min-w-0 border border-border bg-background p-6 shadow-[0_18px_45px_rgba(11,36,32,0.16)] sm:p-8 ${showSummaryMobile ? '' : 'hidden lg:block'}`} aria-hidden="true">
          <Skeleton className="h-5 w-28" />
          <div className="mt-6 flex flex-col gap-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
          </div>
          <div className="mt-6 border-t border-border pt-6">
            <Skeleton className="h-7 w-32" />
            <Skeleton className="mt-6 h-12 w-full rounded-full" />
          </div>
        </section>
      </main>
    </div>
  );
}
