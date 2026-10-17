import { Skeleton } from '@/components/skeleton';

/** Estructura de la sede: cabecera, héroe, bloque de paquetes. Es el límite de carga de toda la página. */
export default function CargandoSede() {
  return (
    <div className="min-h-dvh bg-background" aria-hidden="true">
      <div className="fixed inset-x-0 top-0 z-40 border-b border-border bg-background">
        <div className="mx-auto flex h-20 max-w-[1440px] items-center justify-between px-6 sm:px-8">
          <Skeleton className="h-11 w-32" />
          <Skeleton className="h-11 w-11" />
        </div>
      </div>

      <section className="px-6 pb-16 pt-[calc(var(--nav-alto)+3rem)] sm:px-8 lg:px-12">
        <div className="mx-auto max-w-6xl">
          <Skeleton className="h-14 w-3/4 max-w-xl" />
          <Skeleton className="mt-5 h-5 w-full max-w-lg" />
          <Skeleton className="mt-8 h-14 w-full max-w-3xl" />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-12 sm:px-8 lg:px-12">
        <Skeleton className="mb-8 h-10 w-64" />
        <div className="grid gap-8 md:grid-cols-2">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </section>
    </div>
  );
}
