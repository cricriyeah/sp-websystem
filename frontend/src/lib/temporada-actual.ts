// Qué temporada de la sede toca en un mes dado (F10). Los meses del contenido vienen como abreviaturas
// localizadas («Dic», «Dec»): se reconocen las de es y en, por sus tres primeras letras. Sin imports: lo
// prueba el runner.

const MESES = [
  ['ene', 'jan'],
  ['feb'],
  ['mar'],
  ['abr', 'apr'],
  ['may'],
  ['jun'],
  ['jul'],
  ['ago', 'aug'],
  ['sep'],
  ['oct'],
  ['nov'],
  ['dic', 'dec'],
] as const;

const NUMERO_DE_MES = new Map<string, number>(MESES.flatMap((nombres, i) => nombres.map((n) => [n, i] as const)));

function numeroDeMes(abreviatura: string): number | undefined {
  const base = abreviatura.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().slice(0, 3);
  return NUMERO_DE_MES.get(base);
}

/** El índice de la fila que cubre el mes (0 a 11, como `Date.getMonth()`), o -1 si ninguna lo cubre. */
export function temporadaDeMes(filas: readonly { meses: readonly string[] }[], mes: number): number {
  return filas.findIndex((fila) => fila.meses.some((m) => numeroDeMes(m) === mes));
}
