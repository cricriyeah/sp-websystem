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
 */
export function SelectorIdioma({ lang, label }: { lang: Locale; label: string }) {
  const router = useRouter();
  const pathname = usePathname();

  const cambiar = (idioma: Locale) => {
    if (idioma === lang) return;
    // `usePathname()` no trae el query: sin él se perderían `?paso=`, `?moneda=` y el origen.
    router.push(pathname.replace(/^\/(es|en)/, `/${idioma}`) + window.location.search);
  };

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
            className={`flex size-11 items-center justify-center rounded-control texto-pequeno transition-colors ${
              activo ? 'bg-cafe-bruma font-semibold text-cafe' : 'text-muted hover:text-foreground'
            }`}
          >
            {texto}
          </Button>
        );
      })}
    </div>
  );
}
