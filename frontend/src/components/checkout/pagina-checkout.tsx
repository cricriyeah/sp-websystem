'use client';

import type { ReactNode } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { BarraInferior } from '@/components/reserva/barra-inferior';
import { CabeceraMinima } from '@/components/reserva/cabecera-minima';
import { ProveedorBarra } from '@/components/reserva/contexto-barra';
import { LineaProgreso } from '@/components/reserva/linea-progreso';
import { useMovil } from '@/components/reserva/use-movil';

type Props = {
  lang: Locale;
  dict: Dictionary;
  volverHref: string;
  volverLabel: string;
  /**
   * La flecha es una sola: «paso anterior» mientras haya uno al que volver y, en el primero,
   * «salir» al origen (`volverHref`). Sin esta función, siempre sale.
   */
  alPasoAnterior?: () => void;
  /** Checkout de una sola empresa: su sello va junto a la marca (`CabeceraMinima`). */
  empresa?: { nombre: string; logo?: string };
  /** Hay dinero retenido: la marca de la cabecera no enlaza. */
  marcaFija?: boolean;
  /** `EncabezadoCompra`. */
  encabezado: ReactNode;
  /** Aviso a todo el ancho entre el encabezado y el stepper (p. ej. día sin lugar). */
  aviso?: ReactNode;
  stepper: { actual: number; steps?: string[]; totalMovil?: string; rotulo?: string; totalGeneral?: string; etiquetasCortas?: string[] };
  /** Columna izquierda: las tarjetas de paso. */
  pasos: ReactNode;
  /** Columna derecha: `StripePanel`. */
  pedido: ReactNode;
};

/**
 * Esqueleto único del checkout: volver → qué compras → stepper → [pasos |
 * pedido] → footer. Sin `sticky` en la columna del pedido (decisión previa:
 * no persigue el scroll).
 */
export function PaginaCheckout({
  lang, dict, volverHref, volverLabel, alPasoAnterior, empresa, marcaFija, encabezado, aviso, stepper, pasos, pedido,
}: Props) {
  const movil = useMovil();
  const nombres: [string, string, string] = [dict.checkout.stepper.viaje, dict.checkout.stepper.datos, dict.checkout.stepper.pago];
  return (
    <ProveedorBarra>
    <div className="min-h-dvh bg-background">
      <CabeceraMinima
        lang={lang}
        nav={dict.nav}
        volverHref={volverHref}
        volverLabel={volverLabel}
        alPasoAnterior={alPasoAnterior}
        empresa={empresa}
        marcaFija={marcaFija}
      />

      {/* La cabecera es `fixed` y no reserva espacio: `--nav-alto` (globals.css) la
          compensa. El 1.5rem es la separación de siempre. */}
      <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
        {encabezado}
      </div>

      {aviso}

      {/* Escritorio y tablet: la línea de progreso va arriba, sin cifra (el total vive en el resumen).
          En móvil la lleva la barra inferior. */}
      <LineaProgreso
        className="mx-auto mt-4 max-w-6xl px-6 max-sm:hidden sm:px-8 lg:px-12"
        actual={stepper.actual}
        nombres={nombres}
        plantilla={dict.checkout.stepper.stepOf}
      />

      {/* 3fr/2fr: los pasos necesitan el ancho, el pedido es una columna de cifras. */}
      <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 max-sm:pb-[calc(var(--barra-alto)+16px)] sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex min-w-0 flex-col gap-6">{pasos}</div>
        <div className="min-w-0">{pedido}</div>
      </main>

      <CheckoutFooter lang={lang} footer={dict.footer} nav={dict.nav} />
      {movil && (
        <BarraInferior
          checkout={dict.checkout}
          actual={stepper.actual}
          total={stepper.totalMovil}
          estimado={stepper.actual < 3}
        />
      )}
    </div>
    </ProveedorBarra>
  );
}
