import type { Locale } from '@/app/[lang]/dictionaries';

// El sitio se sirve en /es y /en, pero el negocio opera en La Paz, BCS: precios
// y fechas se formatean con la convencion del pais, no con la del idioma a secas.
// `Intl` con 'es' pelado aplica formato de España (4500,00 MXN) en vez del
// mexicano ($4,500.00), asi que el mapeo va explicito.
const INTL_LOCALE: Record<Locale, string> = {
  es: 'es-MX',
  en: 'en-US',
};

export const intlLocale = (lang: Locale) => INTL_LOCALE[lang];
