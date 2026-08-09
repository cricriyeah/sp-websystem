import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const locales = ['es', 'en'] as const;
const defaultLocale = 'es';

function getLocale(request: NextRequest): string {
  const acceptLanguage = request.headers.get('accept-language') ?? '';
  const preferred = acceptLanguage.split(',')[0]?.split('-')[0];
  return locales.includes(preferred as (typeof locales)[number]) ? preferred! : defaultLocale;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const pathnameHasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  );
  if (pathnameHasLocale) return;

  const locale = getLocale(request);
  request.nextUrl.pathname = `/${locale}${pathname}`;
  return NextResponse.redirect(request.nextUrl);
}

export const config = {
  matcher: [
    // Excluye _next, archivos estaticos y metadata files.
    '/((?!_next|api|favicon.ico|sitemap.xml|robots.txt).*)',
  ],
};
