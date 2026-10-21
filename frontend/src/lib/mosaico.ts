// Cómo se reparte el mosaico de la galería (F10) en una cuadrícula de 12 columnas, sin huecos: filas
// de 2 y de 3 fotos, alternadas, y una fila de 1 o de 4 al final si sobrarían. Sin imports: lo prueba
// el runner.

const TAMANOS_DE_FILA = [2, 3] as const;

/** Cuántas fotos lleva cada fila, para `n` fotos. Nunca deja una foto sola salvo que sea la única. */
export function tamanosDeFilas(n: number): number[] {
  const filas: number[] = [];
  let resto = n;
  while (resto > 0) {
    let tamano: number = Math.min(TAMANOS_DE_FILA[filas.length % 2], resto);
    if (resto - tamano === 1) tamano = resto;
    filas.push(tamano);
    resto -= tamano;
  }
  return filas;
}

/** Columnas (de 12) de cada foto en escritorio; cada fila suma 12. */
export function columnasDeMosaico(n: number): number[] {
  return tamanosDeFilas(n).flatMap((tamano, fila) => {
    if (tamano === 1) return [12];
    if (tamano === 2) return fila % 2 === 0 ? [7, 5] : [5, 7];
    return Array<number>(tamano).fill(12 / tamano);
  });
}
