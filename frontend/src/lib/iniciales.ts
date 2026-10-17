// Módulo puro, SIN imports (lo compila el runner de pruebas).

// Conectores que no cuentan como palabra del nombre: «Sal y Sol» es SS, no SY.
// «La» NO está aquí a propósito: «La Ventana Travel» es LV.
const CONECTORES = new Set(['y', 'e', 'and', '&', 'de', 'del', 'of']);

/**
 * Monograma de una empresa: la inicial de sus dos primeras palabras (sin contar
 * conectores), en mayúscula. Una sola palabra da una sola inicial; vacío da vacío.
 */
export function iniciales(nombre: string): string {
  const letras: string[] = [];
  for (const palabra of nombre.trim().split(/\s+/)) {
    if (CONECTORES.has(palabra.toLowerCase())) continue;
    // Primera letra o dígito: «(Sal)» da S, y un guion suelto no da nada.
    const inicial = palabra.match(/[\p{L}\p{N}]/u)?.[0];
    if (!inicial) continue;
    letras.push(inicial.toLocaleUpperCase('es'));
    if (letras.length === 2) break;
  }
  return letras.join('');
}
