import type { Locale } from '@/app/[lang]/dictionaries';

function anclaNormalizada(ancla?: string): string {
  if (!ancla) return '';
  return ancla.startsWith('#') ? ancla : `#${ancla}`;
}

export function hrefInicio(lang: Locale, ancla?: string): string {
  return `/${lang}${anclaNormalizada(ancla)}`;
}

export function hrefSede(lang: Locale, slug: string, ancla?: string): string {
  return `/${lang}/sede/${encodeURIComponent(slug)}${anclaNormalizada(ancla)}`;
}
