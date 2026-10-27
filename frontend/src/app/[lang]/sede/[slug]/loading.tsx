import { VeloCargando } from '@/components/isotipo-cargando';
import { Skeleton } from '@/components/skeleton';

/** Estructura de la sede: cabecera, arranque a pantalla completa y la fila de «Qué puedes reservar». Es el límite de carga de toda la página. */
export default function CargandoSede() {
  return (
    <>
      <VeloCargando />
    <div className="min-h-dvh bg-background" aria-hidden="true">
      <div className="fixed inset-x-0 top-0 z-40 bg-superficie shadow-tarjeta">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-pagina">
          <Skeleton className="size-11 rounded-full" />
          <Skeleton className="h-11 w-40 rounded-full" />
        </div>
      </div>

      <Skeleton className="mt-[var(--nav-alto)] h-[max(28.75rem,calc(100svh-var(--nav-alto)))] w-full bg-tinta" />

      <section className="mx-auto max-w-[1440px] px-pagina py-16">
        <Skeleton className="mb-8 h-10 w-64" />
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="aspect-[4/5] w-full" />
          <Skeleton className="aspect-[4/5] w-full" />
          <Skeleton className="aspect-[4/5] w-full md:col-span-2 lg:col-span-1" />
        </div>
      </section>
    </div>
    </>
  );
}
