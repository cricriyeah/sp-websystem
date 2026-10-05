'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

/**
 * Pie de una tarjeta de paso, con el único CTA primario. Un solo elemento con
 * dos estados:
 *
 * - **Natural** (el CTA queda a la vista al final de la tarjeta): se ve como
 *   un pie normal, sin nada especial.
 * - **Fijo** (en escritorio, el sitio natural queda bajo la pantalla): se
 *   queda pegado al borde inferior y pasa a verse como una capa — fondo
 *   translúcido con desenfoque, borde y sombra hacia arriba, el mismo lenguaje
 *   que el stepper de arriba — con el título de la tarjeta a la izquierda para
 *   que se sepa qué se está confirmando aunque el título ya haya salido de
 *   pantalla.
 *
 * Antes era una banda blanca plana siempre pegada: cortaba el contenido a
 * mitad de un elemento sin ninguna pista de que fuera una capa flotante, y
 * robaba alto incluso cuando el botón natural ya se veía.
 *
 * Es un solo botón en el DOM (sin duplicado), así que el foco por teclado no
 * se pierde. Mientras está fijo se reserva `scroll-padding-bottom` para que un
 * campo enfocado no quede tapado por la barra.
 */
export function PieDeTarjeta({ titulo, children }: { titulo: string; children: ReactNode }) {
  const marca = useRef<HTMLDivElement>(null);
  const pie = useRef<HTMLDivElement>(null);
  const [fijo, setFijo] = useState(false);

  // La marca vive en el sitio natural del pie (fuera de él: dentro se movería
  // con el `sticky`). Si no se ve y está por debajo de la pantalla, el pie está
  // pegado al borde.
  useEffect(() => {
    const elemento = marca.current;
    if (!elemento) return;
    const observador = new IntersectionObserver(([entrada]) => {
      const debajo = entrada.boundingClientRect.top > (entrada.rootBounds?.bottom ?? window.innerHeight);
      setFijo(!entrada.isIntersecting && debajo);
    });
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);

  useEffect(() => {
    if (!fijo) return;
    const raiz = document.documentElement;
    const previo = raiz.style.scrollPaddingBottom;
    raiz.style.scrollPaddingBottom = `${(pie.current?.offsetHeight ?? 0) + 16}px`;
    return () => {
      raiz.style.scrollPaddingBottom = previo;
    };
  }, [fijo]);

  return (
    <>
      <div ref={marca} aria-hidden className="mt-6" />
      <div
        ref={pie}
        className={`-mx-6 flex items-center justify-between gap-4 border-t border-border bg-background px-6 pt-5 transition-shadow duration-200 sm:-mx-8 sm:px-8 lg:sticky lg:bottom-0 lg:z-10 lg:pb-4 ${
          fijo ? 'lg:bg-background/95 lg:shadow-[0_-12px_30px_rgba(11,36,32,0.12)] lg:backdrop-blur-sm' : ''
        }`}
      >
        <span
          aria-hidden
          className={`hidden min-w-0 truncate text-sm font-medium text-muted transition-opacity duration-200 lg:block ${
            fijo ? 'opacity-100' : 'opacity-0'
          }`}
        >
          {titulo}
        </span>
        <div className="ml-auto shrink-0">{children}</div>
      </div>
    </>
  );
}
