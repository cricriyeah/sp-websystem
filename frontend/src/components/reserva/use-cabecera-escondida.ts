'use client';

import { useEffect, useState, type RefObject } from 'react';

/** Recorrido seguido hacia abajo antes de esconder: los micro-scrolls no la hacen temblar. */
const BAJAR_PX = 12;
/** Recorrido seguido hacia arriba para que vuelva (subir a propósito, no un rebote del dedo). */
const SUBIR_PX = 16;
/** Tras enfocar un campo o cambiar el alto visible (teclado), el scroll que provoca el navegador no cuenta. */
const PAUSA_MS = 500;

/**
 * La cabecera del checkout móvil cede su sitio al bajar y vuelve al subir o al llegar arriba (derivación PFD,
 * 2026-10-29: «solo en el tope» obligaría a subir toda la pantalla para volver al paso anterior o pedir ayuda).
 * Nunca se esconde en la franja de arriba (cada pantalla nueva del asistente arranca ahí), ni con el foco dentro de
 * ella (teclado o selector de idioma abierto). Listener pasivo y un cálculo por cuadro; el movimiento es CSS
 * (`.barra-escondible`), que retoma desde donde va si el cliente cambia de dirección a medio camino.
 */
export function useCabeceraEscondida(activo: boolean, barra: RefObject<HTMLElement | null>): boolean {
  const [oculta, setOculta] = useState(false);

  useEffect(() => {
    if (!activo) return;
    let ultimo = window.scrollY;
    let recorrido = 0;
    let cuadro = 0;
    let pausaHasta = 0;
    // `null`: el primer cálculo siempre fija el estado (pudo quedar oculta de una activación anterior).
    let escondida: boolean | null = null;

    const fijar = (valor: boolean) => {
      if (valor === escondida) return;
      escondida = valor;
      setOculta(valor);
    };

    const revisar = () => {
      cuadro = 0;
      const y = Math.max(0, window.scrollY);
      const delta = y - ultimo;
      ultimo = y;
      if (y <= (barra.current?.offsetHeight ?? 0)) {
        recorrido = 0;
        fijar(false);
        return;
      }
      if (performance.now() < pausaHasta || barra.current?.contains(document.activeElement)) {
        recorrido = 0;
        return;
      }
      if (delta === 0) return;
      if (Math.sign(delta) !== Math.sign(recorrido)) recorrido = 0;
      recorrido += delta;
      if (recorrido >= BAJAR_PX) fijar(true);
      else if (recorrido <= -SUBIR_PX) fijar(false);
    };

    const alScroll = () => {
      if (!cuadro) cuadro = requestAnimationFrame(revisar);
    };
    const pausar = () => {
      pausaHasta = performance.now() + PAUSA_MS;
    };
    const alEnfocar = (evento: FocusEvent) => {
      pausar();
      if (barra.current?.contains(evento.target as Node)) fijar(false);
    };

    cuadro = requestAnimationFrame(revisar);
    window.addEventListener('scroll', alScroll, { passive: true });
    window.visualViewport?.addEventListener('resize', pausar);
    document.addEventListener('focusin', alEnfocar);
    return () => {
      cancelAnimationFrame(cuadro);
      window.removeEventListener('scroll', alScroll);
      window.visualViewport?.removeEventListener('resize', pausar);
      document.removeEventListener('focusin', alEnfocar);
    };
  }, [activo, barra]);

  return activo && oculta;
}
