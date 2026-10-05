'use client';

import type { ReactNode } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

/**
 * Cambia de semana deslizando en la dirección del click: adelante entra por la
 * derecha, atrás por la izquierda. Una dirección coherente le dice al ojo qué
 * viene; redibujar los 7 días de golpe no le da nada que predecir.
 */
export function Deslizable({ clave, direccion, children, className }: {
  clave: string; direccion: 1 | -1; children: ReactNode; className?: string;
}) {
  const sinMovimiento = useReducedMotion();
  const desplazamiento = sinMovimiento ? 0 : 20;
  // `custom` en el AnimatePresence y en el hijo: el que se va usa la dirección
  // NUEVA (la del click), no la que tenía cuando se pintó. Sin esto, al invertir
  // el sentido el contenido saliente se iba hacia el lado equivocado.
  const variantes = {
    entra: (d: 1 | -1) => ({ opacity: 0, x: d * desplazamiento }),
    centro: { opacity: 1, x: 0 },
    sale: (d: 1 | -1) => ({ opacity: 0, x: -d * desplazamiento }),
  };
  return (
    <AnimatePresence mode="wait" initial={false} custom={direccion}>
      <motion.div key={clave} className={className} custom={direccion} variants={variantes}
        initial="entra" animate="centro" exit="sale"
        transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
