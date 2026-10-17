'use client';

import { useState, type ReactNode } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { transicion } from '@/lib/movimiento';

/**
 * Abre y pliega un bloque sin saltos: altura y opacidad en una sola curva
 * (`duracion-media`, `curva-estandar`), la misma que usa `CheckoutSectionCard`. Todo lo que aparece o desaparece dentro
 * del checkout pasa por aquí: un cambio instantáneo es un error de predicción
 * para quien mira (el contenido de abajo brinca) y una curva común hace que
 * todo el flujo se sienta de una sola pieza.
 *
 * Con "reducir movimiento" solo cambia la opacidad. El contenido plegado no
 * queda en el árbol.
 */
export function Despliegue({
  abierto,
  children,
  className,
}: {
  abierto: boolean;
  children: ReactNode;
  className?: string;
}) {
  const sinMovimiento = useReducedMotion();
  // `overflow-hidden` solo mientras la altura está a medias: asentado, recortaría
  // el anillo de foco o la sombra de un hijo contra el borde exacto de la caja.
  const [enTransicion, setEnTransicion] = useState(false);

  return (
    <AnimatePresence initial={false}>
      {abierto && (
        <m.div
          key="despliegue"
          initial={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }}
          animate={sinMovimiento ? { opacity: 1 } : { height: 'auto', opacity: 1 }}
          exit={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }}
          transition={transicion(sinMovimiento)}
          onAnimationStart={() => setEnTransicion(true)}
          onAnimationComplete={() => setEnTransicion(false)}
          className={`${enTransicion ? 'overflow-hidden' : 'overflow-visible'} ${className ?? ''}`}
        >
          {children}
        </m.div>
      )}
    </AnimatePresence>
  );
}
