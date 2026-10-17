import { Skeleton } from '@/components/skeleton';

/** Estructura del detalle de servicio: volver, título, descripción, precio y botón. */
export default function CargandoServicio() {
  return (
    <div className="min-h-dvh bg-background" aria-hidden="true">
      <div className="fixed inset-x-0 top-0 z-40 border-b border-border bg-superficie">
        <div className="mx-auto flex h-20 max-w-[1440px] items-center justify-between px-6 sm:px-8">
          <Skeleton className="h-11 w-32" />
          <Skeleton className="h-11 w-11" />
        </div>
      </div>

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-[calc(var(--nav-alto)+3rem)] sm:px-8 lg:px-12">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-8 h-14 w-3/4 max-w-3xl" />
        <Skeleton className="mt-5 h-5 w-full max-w-3xl" />
        <Skeleton className="mt-2 h-5 w-2/3 max-w-2xl" />
        <Skeleton className="mt-6 h-7 w-56" />
        <Skeleton className="mt-8 h-12 w-44 rounded-full" />
      </section>
    </div>
  );
}
