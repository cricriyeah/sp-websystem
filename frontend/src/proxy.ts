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
    // Excluye _next, la API y **cualquier ruta con punto**, que es como se
    // reconoce un archivo servido desde /public: el logo, los iconos, el
    // favicon, sitemap.xml, robots.txt. Sin el `.*\..*`, una peticion a
    // /logos/logo.png se redirigia a /es/logos/logo.png —que no existe— y la
    // imagen salia rota; el optimizador de next/image devolvia 400 al recibir
    // una redireccion en vez del archivo.
    '/((?!_next|api|.*\..*).*)',
  ],
};
