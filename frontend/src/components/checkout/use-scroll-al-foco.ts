'use client';

import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'motion/react';

/**
 * Lleva al cliente a la tarjeta en foco cuando él cambia de paso (confirmó uno
 * o reabrió una respuesta). La tarjeta en foco lleva `data-tarjeta-foco` y su
 * `scroll-margin-top` ya deja libre el header fijo y el stepper.
 *
 * - Solo se mueve si hace falta: si el borde superior de la tarjeta ya se ve
 *   en la parte alta de la pantalla, no se toca nada.
 * - Espera a que termine el colapso de la tarjeta anterior (el contenido de
 *   arriba cambia de altura y medir antes daría una posición que ya no existe).
 * - No corre al cargar la página, solo ante un cambio posterior de `clave`.
 * - Con "reducir movimiento" el desplazamiento es instantáneo.
 */
export function useScrollAlFoco(clave: string) {
  const primera = useRef(true);
  const sinMovimiento = useReducedMotion();

  useEffect(() => {
    if (primera.current) {
      primera.current = false;
      return;
    }
    const id = window.setTimeout(() => {
      const tarjeta = document.querySelector<HTMLElement>('[data-tarjeta-foco]');
      if (!tarjeta) return;
      const margen = parseFloat(getComputedStyle(tarjeta).scrollMarginTop) || 0;
      const { top } = tarjeta.getBoundingClientRect();
      const yaSeVe = top >= margen - 4 && top <= window.innerHeight * 0.55;
      if (yaSeVe) return;
      tarjeta.scrollIntoView({ block: 'start', behavior: sinMovimiento ? 'auto' : 'smooth' });
    }, 320);
    return () => window.clearTimeout(id);
  }, [clave, sinMovimiento]);
}
