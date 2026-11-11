/**
 * Idioma con el que se abre el sitio cuando la URL no lo trae (`proxy.ts`), según `Accept-Language`.
 *
 * Plan de marketing (2026-11-11): quien no lee español ni inglés (un francés, un alemán) entiende mejor el inglés,
 * así que va a `/en`. Se respeta el orden y los pesos `q` del navegador: «fr, en;q=0.8, es;q=0.5» va en inglés y
 * «de, es» en español. Sin cabecera (buscadores, curl) se queda el español, que es el mercado de la casa.
 */
export type Idioma = 'es' | 'en';

export function idiomaDeCabecera(cabecera: string | null | undefined): Idioma {
  const texto = (cabecera ?? '').trim();
  if (!texto) return 'es';

  const preferidos = texto
    .split(',')
    .map((parte, orden) => {
      const [etiqueta, ...params] = parte.trim().split(';');
      const q = params.map((p) => p.trim()).find((p) => p.startsWith('q='));
      const peso = q ? Number(q.slice(2)) : 1;
      return { idioma: etiqueta.trim().split('-')[0].toLowerCase(), peso: Number.isFinite(peso) ? peso : 0, orden };
    })
    .filter((p) => p.idioma && p.peso > 0)
    .sort((a, b) => b.peso - a.peso || a.orden - b.orden);

  for (const { idioma } of preferidos) {
    if (idioma === 'es' || idioma === 'en') return idioma;
  }
  return 'en';
}
