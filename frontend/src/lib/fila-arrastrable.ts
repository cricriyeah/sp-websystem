// La lógica de la fila que se arrastra (F10): si desborda, cuánto se ha recorrido y a dónde lleva
// cada flecha. Sin imports ni DOM: recibe las medidas del carril. Lo prueba el runner.

export type MedidasFila = { scrollLeft: number; scrollWidth: number; clientWidth: number };

/** Tolerancia de subpíxeles al llegar a un extremo. */
const MARGEN = 2;

export type EstadoFila = {
  /** Hay más fila de la que cabe: solo entonces se pintan flechas y barra de avance. */
  desborda: boolean;
  /** 0 a 1: hasta dónde llega lo que se ve (el borde derecho del carril sobre el largo total). */
  avance: number;
  puedeAtras: boolean;
  puedeAdelante: boolean;
};

export function estadoDeFila({ scrollLeft, scrollWidth, clientWidth }: MedidasFila): EstadoFila {
  const desborda = scrollWidth - clientWidth > MARGEN;
  if (!desborda) return { desborda: false, avance: 1, puedeAtras: false, puedeAdelante: false };
  return {
    desborda: true,
    avance: Math.min(1, Math.max(0, (scrollLeft + clientWidth) / scrollWidth)),
    puedeAtras: scrollLeft > MARGEN,
    puedeAdelante: scrollLeft + clientWidth < scrollWidth - MARGEN,
  };
}

/** A dónde lleva una flecha: casi un carril entero, para que asome la última tarjeta vista. */
export function destinoDeFila({ scrollLeft, scrollWidth, clientWidth }: MedidasFila, sentido: -1 | 1): number {
  const destino = scrollLeft + sentido * clientWidth * 0.8;
  return Math.min(Math.max(0, destino), Math.max(0, scrollWidth - clientWidth));
}

/**
 * La tarjeta que encabeza lo que se ve (0 = la primera), para el contador «1 / 3» del teléfono: la de inicio
 * más cercana al recorrido. `inicios` son los bordes izquierdos de las tarjetas medidos desde la primera.
 */
export function indiceDeFila(scrollLeft: number, inicios: number[]): number {
  let mejor = 0;
  for (let i = 1; i < inicios.length; i++) {
    if (Math.abs(inicios[i] - scrollLeft) < Math.abs(inicios[mejor] - scrollLeft)) mejor = i;
  }
  return mejor;
}
