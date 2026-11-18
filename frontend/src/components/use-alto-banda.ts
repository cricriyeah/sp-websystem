'use client';

import { useEffect, type RefObject } from 'react';

/**
 * La banda «Continuar reservación» va pegada bajo la barra flotante y suma su alto a `--nav-alto` por `--banda-alto`
 * (globals.css): así las páginas bajan solas sin saber que existe. Sin banda vale 0. El regreso no suma nada: es la
 * esquina del logo, dentro de la barra.
 */
export function useAltoBanda(ref: RefObject<HTMLElement | null>, activa: boolean) {
  useEffect(() => {
    const banda = ref.current;
    if (!banda || !activa) return;
    const raiz = document.documentElement;
    const medir = () => raiz.style.setProperty('--banda-alto', `${banda.getBoundingClientRect().height}px`);
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(banda);
    return () => { observador.disconnect(); raiz.style.removeProperty('--banda-alto'); };
  }, [ref, activa]);
}
