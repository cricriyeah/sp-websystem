'use client';

import { usePathname, useRouter } from 'next/navigation';
import type { Locale } from '@/app/[lang]/dictionaries';
import { Button } from '@/components/ui/button';

const IDIOMAS = [
  { valor: 'es', texto: 'ES' },
  { valor: 'en', texto: 'EN' },
] as const;

/**
 * Idioma en dos segmentos «ES | EN» de 44 px: un toque, sin bandera ni desplegable. Es el mismo
 * en la cabecera del sitio y en la del checkout. El cambio conserva la ruta y el query
 * (`?paso=`, `?moneda=`, `?origen=`) y el borrador de la reserva se repone solo.
 *
 * `campana` (el sitio público, F10): un switch, píldora con un círculo negro que se desliza al activo. `estandar` es el de la cabecera del
 * checkout, que no se rediseña.
 */
export function SelectorIdioma({ lang, label, variante = 'estandar' }: { lang: Locale; label: string; variante?: 'estandar' | 'campana' }) {
  const router = useRouter();
  const pathname = usePathname();

  const cambiar = (idioma: Locale) => {
    if (idioma === lang) return;
    // `usePathname()` no trae el query: sin él se perderían `?paso=`, `?moneda=` y el origen.
    router.push(pathname.replace(/^\/(es|en)/, `/${idioma}`) + window.location.search);
  };

  if (variante === 'campana') {
    // Un switch de verdad: todo el control es un solo botón que pasa al otro idioma; el círculo negro se
    // desliza bajo el idioma activo.
    const enIngles = lang === 'en';
    return (
      <Button
        variante="libre"
        type="button"
        role="switch"
        aria-checked={enIngles}
        aria-label={label}
        onClick={() => cambiar(enIngles ? 'es' : 'en')}
        className="relative flex items-center rounded-full bg-cafe-bruma transition-transform duration-150 active:scale-[0.97] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-0 top-0 size-11 rounded-full bg-tinta transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none"
          style={{ transform: `translateX(${enIngles ? 100 : 0}%)` }}
        />
        {IDIOMAS.map(({ valor, texto }) => (
          <span
            key={valor}
            lang={valor}
            className={`relative flex size-11 items-center justify-center texto-cuerpo transition-colors duration-300 ${valor === lang ? 'font-semibold text-white' : 'text-foreground'}`}
          >
            {texto}
          </span>
        ))}
      </Button>
    );
  }

  return (
    <div role="group" aria-label={label} className="flex items-center">
      {IDIOMAS.map(({ valor, texto }) => {
        const activo = valor === lang;
        return (
          <Button
            key={valor}
            variante="libre"
            type="button"
            lang={valor}
            aria-current={activo ? 'true' : undefined}
            onClick={() => cambiar(valor)}
            className={`flex size-11 items-center justify-center rounded-control texto-pequeno transition-colors ${activo ? 'bg-cafe-bruma font-semibold text-cafe' : 'text-muted hover:text-foreground'}`}
          >
            {texto}
          </Button>
        );
      })}
    </div>
  );
}
