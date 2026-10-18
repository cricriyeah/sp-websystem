// Texto que el backend guarda por idioma ({ es, en }): descripción de un extra, «qué incluye»…
// Sin imports: lo corre el runner de pruebas.

export type TextoLocalizado = { es?: string; en?: string };

/** El idioma pedido; si falta, el otro; si no hay nada, ''. */
export function textoLocalizado(valor: TextoLocalizado | null | undefined, lang: 'es' | 'en'): string {
  if (!valor || typeof valor !== 'object') return '';
  const pedido = typeof valor[lang] === 'string' ? valor[lang].trim() : '';
  if (pedido) return pedido;
  const otro = lang === 'es' ? valor.en : valor.es;
  return typeof otro === 'string' ? otro.trim() : '';
}
