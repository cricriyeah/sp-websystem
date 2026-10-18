'use client';

import Link from 'next/link';
import { ArrowLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SelectorIdioma } from '@/components/selector-idioma';
import { Button } from '@/components/ui/button';
import { EmpresaSello } from '@/components/ui/empresa-sello';

type Props = {
  lang: Locale;
  nav: Pick<Dictionary['nav'], 'switchLang'>;
  /** Origen de «salir» (ver `lib/origen.ts`). */
  volverHref: string;
  volverLabel: string;
  /** Con un paso anterior al que volver, la flecha lo hace en vez de salir. */
  alPasoAnterior?: () => void;
  /** Checkout de una sola empresa: su sello va junto al nuestro. Con dos empresas, solo el nuestro. */
  empresa?: { nombre: string; logo?: string };
  /** Hay dinero retenido: la marca deja de ser un enlace para que nadie salga por ahí. */
  marcaFija?: boolean;
};

const MARCA = 'Sun Baja Experience';

/**
 * Cabecera del checkout: flecha, marca e idioma, y nada más. Sin navegación ni WhatsApp (la
 * ayuda vive en `AyudaFlotante`): a media compra cada salida extra compite con pagar. Misma forma
 * que `SiteHeader` (64 px, arena, borde, radio de tarjeta en escritorio) para que parezca el
 * mismo sitio, así que `--nav-alto` no cambia. El idioma conserva `?paso=` y el borrador.
 */
export function CabeceraMinima({ lang, nav, volverHref, volverLabel, alPasoAnterior, empresa, marcaFija = false }: Props) {
  const claseFlecha = 'inline-flex size-12 items-center justify-center rounded-control text-foreground transition-colors hover:bg-cafe-bruma';
  const marca = <EmpresaSello nombre={MARCA} tamano={32} />;

  return (
    <div className="fixed inset-x-0 top-0 z-40 lg:top-4 lg:px-8">
      <header className="mx-auto grid h-16 w-full grid-cols-[48px_1fr_auto] items-center gap-2 border-b border-border bg-arena/95 px-2 backdrop-blur sm:px-4 lg:max-w-[1440px] lg:rounded-card lg:border lg:border-border">
        {alPasoAnterior ? (
          <Button variante="libre" type="button" onClick={alPasoAnterior} aria-label={volverLabel} className={claseFlecha}>
            <ArrowLeft size={20} />
          </Button>
        ) : (
          <Link href={volverHref} aria-label={volverLabel} className={claseFlecha}>
            <ArrowLeft size={20} />
          </Link>
        )}

        <div className="flex min-w-0 items-center justify-center gap-3">
          {marcaFija ? marca : <Link href={`/${lang}`} className="inline-flex">{marca}</Link>}
          {empresa && (
            <>
              <span aria-hidden="true" className="h-6 w-px bg-border" />
              <EmpresaSello nombre={empresa.nombre} logo={empresa.logo} tamano={32} />
            </>
          )}
        </div>

        <SelectorIdioma lang={lang} label={nav.switchLang} />
      </header>
    </div>
  );
}
