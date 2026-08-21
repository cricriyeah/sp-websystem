'use client';

/**
 * Hueco con la forma de lo que esta llegando.
 *
 * Un spinner sustituye la composicion por un punto girando; un skeleton la
 * conserva, y el juicio visual —que se forma en los primeros 50ms— se hace
 * contra la composicion real en vez de contra una pantalla vacia.
 *
 * **Solo donde se conoce la forma.** Para el iframe de Stripe no aplica: es de
 * un tercero, llega cuando llega, y un skeleton que no coincide con lo que
 * aparece despues produce un salto de layout — peor que no poner nada.
 *
 * `animate-pulse` de Tailwind respeta `prefers-reduced-motion` por su cuenta.
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`block animate-pulse rounded-md bg-muted/15 ${className}`}
    />
  );
}

/**
 * Skeleton de una cifra de dinero, con el ancho aproximado del texto que va a
 * reemplazarlo. Existe porque el resumen mostraba un guion `—` en el lugar del
 * precio mientras llegaba la tarifa: una ambiguedad en la pantalla donde menos
 * la quieres.
 */
export function SkeletonPrecio({ className = '' }: { className?: string }) {
  return <Skeleton className={`h-[1em] w-20 align-middle ${className}`} />;
}
