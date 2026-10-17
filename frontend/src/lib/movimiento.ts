// Framer Motion no lee CSS: las duraciones y curvas de docs/design/design.md ("Movimiento")
// viven aquí en segundos y como arreglo de Bézier. tests/movimiento.test.cjs las compara con
// los tokens de globals.css, así que cambiar uno sin el otro falla la prueba.
// Sin imports: el runner de pruebas compila solo `src/` y no resuelve el alias `@/`.

export const DURACION = { corta: 0.15, media: 0.25, larga: 0.4 } as const; // --duracion-corta|media|larga
export type Curva = readonly [number, number, number, number];
export const CURVA_ESTANDAR: Curva = [0.2, 0, 0, 1]; // --curva-estandar: entradas y cambios de estado
export const CURVA_SALIDA: Curva = [0.4, 0, 1, 1]; // --curva-salida

/**
 * Transición de un despliegue o cambio de paso. Con "reducir movimiento" solo se anima la
 * opacidad y en `duracion-corta`: nada se desplaza, escala ni cambia de altura.
 */
export function transicion(sinMovimiento: boolean | null, duracion: number = DURACION.media) {
  return sinMovimiento ? { duration: DURACION.corta } : { duration: duracion, ease: CURVA_ESTANDAR };
}
