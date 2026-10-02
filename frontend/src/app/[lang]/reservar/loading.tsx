import { CheckoutLoadingShell } from '@/components/checkout-loading-shell';
import { Skeleton } from '@/components/skeleton';

/** La ruta sirve tanto servicios como paquetes; muestra solo la estructura común del primer paso. */
export default function CargandoReserva() {
  return (
    <CheckoutLoadingShell>
      <section className="border border-border bg-background p-6 sm:p-8" aria-hidden="true">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="mt-6 h-64 w-full" />
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <Skeleton className="h-12 w-full sm:w-44" />
          <Skeleton className="h-12 w-full sm:w-44" />
        </div>
        <div className="mt-6 flex justify-end border-t border-border pt-5">
          <Skeleton className="h-10 w-32 rounded-full" />
        </div>
      </section>
    </CheckoutLoadingShell>
  );
}
