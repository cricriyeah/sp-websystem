'use client';

import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { cn } from './cn';

/**
 * Una cifra que avisa cuando cambia (el total del pedido): la nueva entra desde abajo mientras la anterior sale
 * hacia arriba, en 220 ms. Con «reducir movimiento» solo cambia la opacidad. Sin cambio, no se mueve nada.
 */
export function CifraViva({ valor, className }: { valor: string | null | undefined; className?: string }) {
  const sinMovimiento = useReducedMotion();
  if (!valor) return null;
  return (
    <span className={cn('relative inline-grid overflow-hidden align-bottom', className)}>
      <AnimatePresence initial={false} mode="popLayout">
        <m.span
          key={valor}
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: '60%' }}
          animate={{ opacity: 1, y: 0 }}
          exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: '-60%' }}
          transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
          className="col-start-1 row-start-1 tabular-nums"
        >
          {valor}
        </m.span>
      </AnimatePresence>
    </span>
  );
}
