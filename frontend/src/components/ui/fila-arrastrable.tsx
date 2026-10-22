'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useReducedMotion } from 'framer-motion';
import { ArrowLeft, ArrowRight } from '@phosphor-icons/react';
import { destinoDeFila, estadoDeFila, type EstadoFila } from '@/lib/fila-arrastrable';
import { Button } from './button';

type Props = {
  /** El encabezado de la fila (el `<h2>` de la sección); las flechas van a su derecha. */
  cabeza: ReactNode;
  /** Nombre accesible del carril: es una región que se enfoca y se recorre con el teclado. */
  etiqueta: string;
  textos: { anterior: string; siguiente: string };
  /** Las tarjetas: cada una crece (`flex-grow`) hasta llenar la fila cuando caben todas. */
  children: ReactNode;
};

const INICIAL: EstadoFila = { desborda: false, avance: 1, puedeAtras: false, puedeAdelante: false };

/**
 * Fila de tarjetas que se arrastra: carril con `scroll-snap` obligatorio (siempre se detiene en una tarjeta, nunca a la mitad de dos), flechas en círculo y una barra de avance de
 * 4 px. Las flechas van junto al título en escritorio y junto a la barra (abajo a la derecha) en el teléfono. Las flechas y la barra solo existen cuando la fila no cabe. Sin JavaScript sigue siendo un carril
 * que se desliza con el dedo. Con «reducir movimiento» las flechas saltan sin deslizar.
 */
export function FilaArrastrable({ cabeza, etiqueta, textos, children }: Props) {
  const carril = useRef<HTMLDivElement>(null);
  const reducido = useReducedMotion();
  const [estado, setEstado] = useState<EstadoFila>(INICIAL);

  const medir = useCallback(() => {
    const el = carril.current;
    if (el) setEstado(estadoDeFila(el));
  }, []);

  useEffect(() => {
    const el = carril.current;
    if (!el) return;
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(el);
    for (const hijo of Array.from(el.children)) observador.observe(hijo);
    return () => observador.disconnect();
  }, [medir]);

  const mover = (sentido: -1 | 1) => {
    const el = carril.current;
    if (el) el.scrollTo({ left: destinoDeFila(el, sentido), behavior: reducido ? 'auto' : 'smooth' });
  };

  const flechas = (
    <>
      <Button variante="campana-gris" tamano="icono" aria-label={textos.anterior} aria-disabled={!estado.puedeAtras} onClick={() => mover(-1)}>
        <ArrowLeft size={20} weight="bold" aria-hidden="true" />
      </Button>
      <Button variante="campana-gris" tamano="icono" aria-label={textos.siguiente} aria-disabled={!estado.puedeAdelante} onClick={() => mover(1)}>
        <ArrowRight size={20} weight="bold" aria-hidden="true" />
      </Button>
    </>
  );

  return (
    <div>
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-end justify-between gap-6 px-4 pb-8 sm:px-6 lg:px-12">
        {cabeza}
        {/* En escritorio, a la derecha del título; en el teléfono bajan junto a la barra, al alcance del pulgar. */}
        {estado.desborda && <div className="flex gap-2 max-sm:hidden">{flechas}</div>}
      </div>
      <div
        ref={carril}
        role="region"
        aria-label={etiqueta}
        tabIndex={0}
        onScroll={medir}
        className="mx-auto flex max-w-[1440px] snap-x snap-mandatory gap-3 overflow-x-auto scroll-px-4 px-4 pb-1 [scrollbar-width:none] sm:scroll-px-6 sm:px-6 lg:scroll-px-12 lg:px-12 [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </div>
      {estado.desborda && (
        <div className="mx-auto mt-7 flex max-w-[1440px] items-center gap-4 px-4 sm:px-6 lg:px-12">
          <div aria-hidden="true" className="h-1 flex-1 overflow-hidden bg-cafe-bruma">
            <span
              className="block h-full origin-left bg-tinta transition-transform duration-[120ms] ease-linear motion-reduce:transition-none"
              style={{ transform: `scaleX(${estado.avance})` }}
            />
          </div>
          <div className="flex gap-2 sm:hidden">{flechas}</div>
        </div>
      )}
    </div>
  );
}
