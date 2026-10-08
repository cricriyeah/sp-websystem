'use client';

import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'motion/react';

/**
 * Una cifra o rótulo que cambia de valor entre pasos ("Total $8,950" →
 * "Pagas ahora $4,450"): entra con un fundido corto en vez de saltar. Con
 * "reducir movimiento" solo cambia la opacidad. `valor` es la llave: mientras
 * no cambie, no se anima.
 */
export function CifraAnimada({ valor, className, children }: { valor: string; className?: string; children: ReactNode }) {
  const sinMovimiento = useReducedMotion();
  return (
    <motion.span
      key={valor}
      initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.span>
  );
}
