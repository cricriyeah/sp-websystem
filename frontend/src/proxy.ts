import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { COOKIE_SOLO_SEDE, SEGUNDOS_SOLO_SEDE, decidirSoloSede } from '@/lib/solo-sede';

const locales = ['es', 'en'] as const;
const defaultLocale = 'es';

function getLocale(request: NextRequest): string {
  const acceptLanguage = request.headers.get('accept-language') ?? '';
  const preferred = acceptLanguage.split(',')[0]?.split('-')[0];
  return locales.includes(preferred as (typeof locales)[number]) ? preferred! : defaultLocale;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Modo «solo sede» (links cortos `/lapaz`, ver lib/solo-sede.ts). Va antes que el idioma:
  // `/lapaz` no trae idioma y se resuelve en una sola redirección, directo a la sede.
  const decision = decidirSoloSede({
    pathname,
    search: request.nextUrl.search,
    cookie: request.cookies.get(COOKIE_SOLO_SEDE)?.value,
    idiomaPreferido: () => getLocale(request) as 'es' | 'en',
    // Sin la cabecera (navegadores viejos, curl) cuenta como carga de página.
    esCargaDePagina: (request.headers.get('sec-fetch-dest') ?? 'document') === 'document',
  });
  if (decision.tipo === 'redirigir') {
    // 307: temporal y sin caché; la misma URL lleva a lugares distintos según la cookie.
    return conCookie(NextResponse.redirect(new URL(decision.destino, request.url), 307), decision.cookie);
  }

  const pathnameHasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  );
  // Sin idioma, la petición que sigue ya con idioma vuelve a decidir la cookie.
  if (pathnameHasLocale) return decision.cookie ? conCookie(NextResponse.next(), decision.cookie) : undefined;

  const locale = getLocale(request);
  request.nextUrl.pathname = `/${locale}${pathname}`;
  return NextResponse.redirect(request.nextUrl);
}

function conCookie(respuesta: NextResponse, cookie: { guardar: string } | 'borrar' | undefined): NextResponse {
  if (cookie === 'borrar') {
    respuesta.cookies.delete(COOKIE_SOLO_SEDE);
  } else if (cookie) {
    respuesta.cookies.set(COOKIE_SOLO_SEDE, cookie.guardar, { path: '/', maxAge: SEGUNDOS_SOLO_SEDE, sameSite: 'lax' });
  }
  return respuesta;
}

export const config = {
  matcher: [
    // Excluye _next, la API y **cualquier ruta con punto**, que es como se
    // reconoce un archivo servido desde /public: el logo, los iconos, el
    // favicon, sitemap.xml, robots.txt. Sin el `.*\..*`, una peticion a
    // /logos/logo.png se redirigia a /es/logos/logo.png —que no existe— y la
    // imagen salia rota; el optimizador de next/image devolvia 400 al recibir
    // una redireccion en vez del archivo.
    // `\\.` y no `\.`: en un string de JS `\.` se vuelve `.` (cualquier carácter) y el patrón
    // dejaba fuera toda ruta de dos letras o más; el proxy solo corría en `/`.
    // `_vercel` y `__next`: rutas internas de Vercel y del servidor de desarrollo, sin idioma.
    '/((?!_next|__next|_vercel|api|.*\\..*).*)',
  ],
};
