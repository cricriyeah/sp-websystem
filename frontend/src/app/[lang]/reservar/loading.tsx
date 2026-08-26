import { Skeleton } from '@/components/skeleton';

/**
 * Lo que se ve mientras el servidor busca la tarifa.
 *
 * La pagina de reserva es un componente de servidor que espera a `getTarifa()`
 * antes de pintar nada. Sin esto, el cliente que toca "Agendar" en la portada se
 * queda en la portada, sin senal de que algo pasa, hasta que la respuesta
 * llega: en un telefono con red de marina eso son varios segundos donde lo
 * razonable es volver a tocar el boton.
 *
 * Es un skeleton y no un spinner porque la forma de esta pantalla ya se conoce
 * —dos tarjetas a la izquierda, el resumen a la derecha— y conservarla deja que
 * el juicio visual se forme contra la composicion real. Sin texto: `loading.tsx`
 * no recibe `params`, asi que no hay idioma que respetar, y un skeleton mudo
 * dice lo mismo en los dos.
 */
export default function CargandoReserva() {
  return (
    <div className="min-h-dvh bg-background">
      {/* Barra del encabezado */}
      <div className="border-b border-border px-6 py-5 sm:px-8 lg:px-12">
        <Skeleton className="h-6 w-32" />
      </div>

      <div className="mx-auto max-w-6xl px-6 pt-6 sm:px-8 lg:px-12">
        <Skeleton className="h-4 w-24" />
      </div>

      <main className="mx-auto grid max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex flex-col gap-6">
          {/* Tarjeta del viaje: calendario, hora y personas */}
          <section className="border border-border bg-surface p-6 sm:p-8">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="mt-6 h-56 w-full" />
            <Skeleton className="mt-5 h-4 w-56" />
            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:gap-4">
              <Skeleton className="h-12 w-full sm:w-44" />
              <Skeleton className="h-12 w-full sm:w-44" />
            </div>
          </section>

          {/* Tarjeta de contacto */}
          <section className="border border-border bg-surface p-6 sm:p-8">
            <Skeleton className="h-5 w-36" />
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
            <Skeleton className="mt-4 h-12 w-full" />
          </section>
        </div>

        {/* Resumen y pago */}
        <section className="border border-border bg-surface p-6 shadow-[0_18px_45px_rgba(11,36,32,0.16)] sm:p-8">
          <Skeleton className="h-5 w-28" />
          <div className="mt-6 flex flex-col gap-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
          </div>
          <Skeleton className="mt-6 h-px w-full" />
          <Skeleton className="mt-6 h-7 w-32" />
          <Skeleton className="mt-6 h-12 w-full rounded-full" />
        </section>
      </main>
    </div>
  );
}
