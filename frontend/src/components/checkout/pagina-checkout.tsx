import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutStepper } from '@/components/checkout-stepper';
import { SiteHeader } from '@/components/site-header';

type Props = {
  lang: Locale;
  dict: Dictionary;
  sedeSlug?: string;
  volverHref: string;
  volverLabel: string;
  /** `EncabezadoCompra`. */
  encabezado: ReactNode;
  /** Aviso a todo el ancho entre el encabezado y el stepper (p. ej. día sin lugar). */
  aviso?: ReactNode;
  stepper: { actual: number; steps?: string[]; totalMovil?: string };
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
  lang, dict, sedeSlug, volverHref, volverLabel, encabezado, aviso, stepper, pasos, pedido,
}: Props) {
  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={dict.nav} variante="sede" sedeSlugActual={sedeSlug} />

      {/* SiteHeader es `fixed` y no reserva espacio: `--nav-alto` (globals.css)
          lo compensa. El 1.5rem es la separación de siempre. */}
      <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
        <Link
          href={volverHref}
          className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {volverLabel}
        </Link>
        {encabezado}
      </div>

      {aviso}

      <CheckoutStepper
        stepper={dict.checkout.stepper}
        actual={stepper.actual}
        steps={stepper.steps}
        totalMovil={stepper.totalMovil}
      />

      {/* 3fr/2fr: los pasos necesitan el ancho, el pedido es una columna de cifras. */}
      <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex min-w-0 flex-col gap-6">{pasos}</div>
        <div className="min-w-0">{pedido}</div>
      </main>

      <CheckoutFooter lang={lang} footer={dict.footer} nav={dict.nav} />
    </div>
  );
}
