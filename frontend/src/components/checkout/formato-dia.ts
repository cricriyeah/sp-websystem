import type { Locale } from '@/app/[lang]/dictionaries';
import { intlLocale } from '@/lib/intl';

/** "Sábado 14 de Marzo" (es) / "Saturday, March 14" (en): el día como se lee en el checkout. */
export function formatDay(date: Date, lang: Locale) {
  const locale = intlLocale(lang);
  const weekday = new Intl.DateTimeFormat(locale, { weekday: 'long' }).format(date);
  const month = new Intl.DateTimeFormat(locale, { month: 'long' }).format(date);
  const day = String(date.getDate()).padStart(2, '0');
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  return lang === 'es'
    ? `${cap(weekday)} ${day} de ${cap(month)}`
    : `${cap(weekday)}, ${cap(month)} ${day}`;
}
