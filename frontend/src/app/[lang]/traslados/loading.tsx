import { CheckoutLoadingShell } from '@/components/checkout-loading-shell';
import { Skeleton } from '@/components/skeleton';

export default function LoadingTraslados() {
  return (
    <CheckoutLoadingShell withTitle showSummaryMobile stepCount={5}>
      <section className="border border-border bg-background p-6 sm:p-8" aria-hidden="true">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="mt-5 h-4 w-64 max-w-full" />
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[1, 2, 3].map((option) => (
            <div key={option} className="rounded-xl border border-border bg-background p-4">
              <Skeleton className="h-5 w-5" />
              <Skeleton className="mt-5 h-4 w-24 max-w-full" />
              <Skeleton className="mt-2 h-3 w-full" />
              <Skeleton className="mt-2 h-3 w-4/5" />
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end border-t border-border pt-5">
          <Skeleton className="h-10 w-32 rounded-full" />
        </div>
      </section>
    </CheckoutLoadingShell>
  );
}
