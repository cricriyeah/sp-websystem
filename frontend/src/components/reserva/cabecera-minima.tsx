'use client';

import { useRef } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BarraFlotante, LogoEmpresaAlLado } from '@/components/barra-flotante';
import { EsquinaBarra, type DestinoEsquina } from '@/components/esquina-barra';
import { SelectorIdioma } from '@/components/selector-idioma';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { empresaEnBarra, etiquetaDeHref } from '@/lib/regreso';
import { useCabeceraEscondida } from './use-cabecera-escondida';
import { useMovil } from './use-movil';
import type { EmpresaDeCompra } from '@/components/checkout/marca-empresa-compra';

type Props = {
  lang: Locale;
  nav: Dictionary['nav'];
  /** Origen de «salir» (ver `lib/origen.ts`). */
  volverHref: string;
  volverLabel: string;
  /** Con un paso anterior al que volver, la esquina lo hace en vez de salir. */
  alPasoAnterior?: () => void;
  /** Checkout de una sola empresa: su logo va junto al nuestro. Con dos empresas, solo el nuestro. */
  empresa?: EmpresaDeCompra;
  /**
   * Hay dinero retenido: la marca deja de ser un enlace para que nadie salga por ahí. La esquina sigue llevando al paso
   * anterior o a la sede, como antes.
   */
  marcaFija?: boolean;
  /** Pago en curso: en el teléfono la barra no se esconde al bajar (ahí pesa más la confianza que el espacio). */
  quieta?: boolean;
};

/**
 * Cabecera del checkout (F10): la misma barra flotante que el hub y las sedes (`BarraFlotante`), sin
 * enlaces de navegación ni WhatsApp (la ayuda vive en `AyudaFlotante`): a media compra cada salida extra
 * compite con pagar. A la izquierda la esquina de regreso (`EsquinaBarra`: ‹ + flama + destino), sin el logo de la
 * empresa (va en el encabezado de la compra; junto al regreso se leería «DESTINOS × SAL Y SOL»); a la derecha, la ayuda y el idioma. Mismo alto que `SiteHeader`, así que `--nav-alto` no cambia. El idioma conserva
 * `?paso=` y el borrador.
 *
 * En el teléfono se esconde al bajar y vuelve al subir o arriba (`useCabeceraEscondida`); la barra inferior con el
 * botón nunca. Con dinero retenido o un pago en curso se queda.
 */
export function CabeceraMinima({ lang, nav, volverHref, volverLabel, alPasoAnterior, empresa, marcaFija = false, quieta = false }: Props) {
  const barra = useRef<HTMLDivElement>(null);
  const movil = useMovil();
  const oculta = useCabeceraEscondida(movil && !marcaFija && !quieta, barra);
  // El regreso del checkout es la misma esquina «‹ + flama + destino» del resto del sitio (2026-11-17): con un paso
  // anterior dice «Paso anterior»; si no, el nombre corto de a dónde sale (la sede, «Detalles», «Paquete»).
  const destino: DestinoEsquina = alPasoAnterior
    ? { etiqueta: nav.regreso.pasoAnterior.corto, aria: nav.regreso.pasoAnterior.aria, alPulsar: alPasoAnterior }
    : { ...(etiquetaDeHref(volverHref, SEDES_INDICE, nav.regreso) ?? { etiqueta: volverLabel, aria: volverLabel }), href: volverHref };

  return (
    <BarraFlotante
      ref={barra}
      oculta={movil ? oculta : undefined}
      inicio={
        // La esquina va fuera de `resto`: así el giro de la flama arranca con la barra y no cuando `resto` ya apareció.
        <EsquinaBarra regreso={destino} hrefLogo={marcaFija ? undefined : `/${lang}`} />
      }
      resto={
        <>
          {/* El logo de la empresa solo va pegado a nuestro logo, nunca junto al regreso: aquí la esquina casi siempre es
              el regreso y la empresa va en el encabezado de la compra (`EncabezadoCompra`). Solo si la salida es el inicio
              y está el modo «solo sede», la esquina es el logo y vuelve la colaboración (`empresaEnBarra`). */}
          <div className="flex min-w-0 items-center gap-3 max-sm:hidden">
            {empresaEnBarra(destino) === 'solo-sede' && (
              <span className="solo-en-sede flex min-w-0 items-center">
                <LogoEmpresaAlLado empresa={empresa} />
              </span>
            )}
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
