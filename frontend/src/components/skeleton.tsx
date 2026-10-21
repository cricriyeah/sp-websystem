'use client';

/**
 * Hueco con la forma de lo que esta llegando.
 *
 * Un spinner sustituye la composicion por un punto girando; un skeleton la
 * conserva, y el juicio visual —que se forma en los primeros 50ms— se hace
 * contra la composicion real en vez de contra una pantalla vacia.
 *
 * **Solo donde se conoce la forma.** El formulario de tarjeta de Stripe tiene su
 * propio esqueleto (`checkout/pago/esqueleto-pago.tsx`): estatico, de altura fija
 * y sin pulso, porque el contenido de pago no se anima y el iframe es de un
 * tercero que llega cuando llega. Este `Skeleton` pulsa: no se usa para pagos.
 *
 * Pulsa 1,2 s y solo para quien no pidio reducir el movimiento. Hereda el radio
 * del elemento que reemplaza: quien lo usa pasa `rounded-*` por `className`.
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`block bg-cafe-bruma motion-safe:animate-[pulso-esqueleto_1.2s_ease-in-out_infinite] ${className}`}
    />
  );
}
