'use client';

import Link from 'next/link';
import { ArrowLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BarraFlotante, LogoEmpresaAlLado, LogoMarca } from '@/components/barra-flotante';
import { SelectorIdioma } from '@/components/selector-idioma';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { Button } from '@/components/ui/button';

type Props = {
  lang: Locale;
  nav: Dictionary['nav'];
  /** Origen de «salir» (ver `lib/origen.ts`). */
  volverHref: string;
  volverLabel: string;
  /** Con un paso anterior al que volver, la flecha lo hace en vez de salir. */
  alPasoAnterior?: () => void;
  /** Checkout de una sola empresa: su logo va junto al nuestro. Con dos empresas, solo el nuestro. */
  empresa?: { nombre: string; logo?: string };
  /** Hay dinero retenido: la marca deja de ser un enlace para que nadie salga por ahí. */
  marcaFija?: boolean;
};

/**
 * Cabecera del checkout (F10): la misma barra flotante que el hub y las sedes (`BarraFlotante`), sin
 * enlaces de navegación ni WhatsApp (la ayuda vive en `AyudaFlotante`): a media compra cada salida extra
 * compite con pagar. A la izquierda la flecha; a la derecha, pegados, nuestro logo, una equis y el de la
 * empresa, y el idioma. Mismo alto que `SiteHeader`, así que `--nav-alto` no cambia. El idioma conserva
 * `?paso=` y el borrador.
 */
export function CabeceraMinima({ lang, nav, volverHref, volverLabel, alPasoAnterior, empresa, marcaFija = false }: Props) {
  const claseFlecha = 'inline-flex size-11 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors hover:bg-borde';
  const marca = <LogoMarca retraso={450} />;

  return (
    <BarraFlotante
      inicio={
        alPasoAnterior ? (
          <Button variante="libre" type="button" onClick={alPasoAnterior} aria-label={volverLabel} className={claseFlecha}>
            <ArrowLeft size={20} />
          </Button>
        ) : (
          <Link href={volverHref} aria-label={volverLabel} className={claseFlecha}>
            <ArrowLeft size={20} />
          </Link>
        )
      }
      resto={
        <>
          <span aria-hidden="true" />
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex min-w-0 items-center gap-3">
              {marcaFija ? marca : <Link href={`/${lang}`} className="inline-flex" aria-label="Sun Baja Experience">{marca}</Link>}
              <LogoEmpresaAlLado empresa={empresa} ocultoEnMovil />
            </div>
            <WhatsappContact nav={nav} variant="icono" />
            <WhatsappContact nav={nav} tone="plain" />
            <SelectorIdioma lang={lang} label={nav.switchLang} variante="campana" />
          </div>
        </>
      }
    />
  );
}
