// Las cifras que cuentan desde cero (F10): «30 %», «48 h». Sin imports ni DOM: lo prueba el runner.

/** Parte una cifra en su número y lo que le sigue; `null` si no empieza con un número entero. */
export function partirCifra(texto: string): { valor: number; sufijo: string } | null {
  const partes = /^(\d+)(.*)$/.exec(texto.trim());
  return partes ? { valor: Number(partes[1]), sufijo: partes[2] } : null;
}

/** El valor que se muestra a mitad de camino: sale rápido y frena al llegar (`progreso` de 0 a 1). */
export function valorContado(meta: number, progreso: number): number {
  const t = Math.min(1, Math.max(0, progreso));
  return Math.round(meta * (1 - (1 - t) ** 3));
}
