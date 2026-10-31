/** «Rogelio, Omar y Dagoberto»: comas entre los nombres y `y` antes del último. */
export function fraseDeNombres(nombres: string[], y: string) {
  if (nombres.length < 2) return nombres.join('');
  return `${nombres.slice(0, -1).join(', ')} ${y} ${nombres.at(-1)}`;
}
