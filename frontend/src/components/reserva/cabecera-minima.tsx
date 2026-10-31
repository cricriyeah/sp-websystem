'use client';

import Link from 'next/link';
import { useRef } from 'react';
import { ArrowLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BarraFlotante, LogoEmpresaAlLado, LogoMarca } from '@/components/barra-flotante';
import { SelectorIdioma } from '@/components/selector-idioma';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { Button } from '@/components/ui/button';
import { useCabeceraEscondida } from './use-cabecera-escondida';
import { useMovil } from './use-movil';

type Props = {
  lang: Locale;
  nav: Dictionary['nav'];
  /** Origen de «salir» (ver `lib/origen.ts`). */
  volverHref: string;
  volverLabel: string;
  /** Con un paso anterior al que volver, la flecha lo hace en vez de salir. */
  alPasoAnterior?: () => void;
  /** Checkout de una sola empresa: su logo va junto al nuestro. Con dos empresas, solo el nuestro. */
  empresa?: { nombre: string; logo?: string; simbolo?: string; simboloBarra?: string };
  /** Hay dinero retenido: la marca deja de ser un enlace para que nadie salga por ahí. */
  marcaFija?: boolean;
  /** Pago en curso: en el teléfono la barra no se esconde al bajar (ahí pesa más la confianza que el espacio). */
  quieta?: boolean;
};

/**
 * Cabecera del checkout (F10): la misma barra flotante que el hub y las sedes (`BarraFlotante`), sin
 * enlaces de navegación ni WhatsApp (la ayuda vive en `AyudaFlotante`): a media compra cada salida extra
 * compite con pagar. A la izquierda la flecha y, pegados a ella, nuestro logo, una equis y el de la
 * empresa; a la derecha, la ayuda y el idioma. Mismo alto que `SiteHeader`, así que `--nav-alto` no cambia. El idioma conserva
 * `?paso=` y el borrador.
 *
 * En el teléfono se esconde al bajar y vuelve al subir o arriba (`useCabeceraEscondida`); la barra inferior con el
 * botón nunca. Con dinero retenido o un pago en curso se queda.
 */
export function CabeceraMinima({ lang, nav, volverHref, volverLabel, alPasoAnterior, empresa, marcaFija = false, quieta = false }: Props) {
  const barra = useRef<HTMLDivElement>(null);
  const movil = useMovil();
  const oculta = useCabeceraEscondida(movil && !marcaFija && !quieta, barra);
  const claseFlecha = 'inline-flex size-11 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors hover:bg-borde';
  const marca = <LogoMarca />;

  return (
    <BarraFlotante
      ref={barra}
      oculta={movil ? oculta : undefined}
      inicio={
        // La marca va con la flecha, fuera de `resto`: así su giro arranca con la barra y no cuando `resto` ya apareció.
        <div className="flex items-center gap-3">
          {alPasoAnterior ? (
            <Button variante="libre" type="button" onClick={alPasoAnterior} aria-label={volverLabel} className={claseFlecha}>
              <ArrowLeft size={20} />
            </Button>
          ) : (
            <Link href={volverHref} aria-label={volverLabel} className={claseFlecha}>
              <ArrowLeft size={20} />
            </Link>
          )}
          {marcaFija ? marca : <Link href={`/${lang}`} className="inline-flex" aria-label="Sun Baja Experience">{marca}</Link>}
        </div>
      }
      resto={
        <>
          <div className="flex min-w-0 items-center gap-3">
            <LogoEmpresaAlLado empresa={empresa} ocultoEnMovil />
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <WhatsappContact nav={nav} variant="icono" />
            <WhatsappContact nav={nav} tone="plain" />
            <SelectorIdioma lang={lang} label={nav.switchLang} variante="campana" />
          </div>
        </>
      }
    />
  );
}
