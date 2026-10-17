// Textos de las paginas de error. Viven aparte del diccionario a proposito:
// `error.tsx` y `global-error.tsx` son componentes de cliente y el diccionario
// (`dictionaries.ts`) es `server-only` y pesa ~56 KB por idioma.

export type IdiomaError = 'es' | 'en';

const TEXTOS = {
  es: {
    titulo: 'Algo salió mal',
    cuerpo: 'No pudimos cargar esta página. Tus datos no se perdieron; intenta de nuevo en unos segundos.',
    reintentar: 'Reintentar',
    inicio: 'Ir al inicio',
  },
  en: {
    titulo: 'Something went wrong',
    cuerpo: "We couldn't load this page. Nothing you entered was lost; please try again in a few seconds.",
    reintentar: 'Try again',
    inicio: 'Go to the home page',
  },
} as const;

/** `useParams().lang` es `string | string[] | undefined`; cualquier otra cosa cae en español. */
export function idiomaDeError(lang: string | string[] | undefined): IdiomaError {
  const valor = Array.isArray(lang) ? lang[0] : lang;
  return valor === 'en' ? 'en' : 'es';
}

export function textosDeError(lang: string | string[] | undefined) {
  const idioma = idiomaDeError(lang);
  return { idioma, ...TEXTOS[idioma] };
}
