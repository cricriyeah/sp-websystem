import { Skeleton } from '@/components/skeleton';

/** Estructura del detalle de servicio y de paquete: arranque, ficha en dos columnas con el bloque de compra. */
export default function CargandoServicio() {
  return (
    <div className="min-h-dvh bg-background" aria-hidden="true">
      <div className="fixed inset-x-0 top-0 z-40 bg-superficie shadow-tarjeta">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 sm:px-6 lg:px-12">
          <Skeleton className="size-11 rounded-full" />
          <Skeleton className="h-11 w-40 rounded-full" />
        </div>
      </div>

      <Skeleton className="mt-[var(--nav-alto)] h-[max(28.75rem,min(70svh,45rem))] w-full bg-tinta" />

      <section className="mx-auto grid max-w-[1440px] gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(20rem,1fr)] lg:gap-24 lg:px-12">
        <div className="flex flex-col gap-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-6 w-full max-w-xl" />
          <Skeleton className="h-6 w-2/3 max-w-lg" />
          <Skeleton className="mt-8 h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
        <Skeleton className="h-80 w-full bg-tinta" />
      </section>
    </div>
  );
}
