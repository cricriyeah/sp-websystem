'use client';

import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { useDeslindeEmpresas } from '@/components/checkout/deslinde-contexto';
import { hrefDeslinde } from '@/lib/routes';

type CheckoutFooterProps = {
  lang: Locale;
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
};

/**
 * Pie minimo del checkout: solo lo legal.
 *
 * El pie del sitio (SiteFooter) trae un CTA "Reservar" y links que llevan de
 * vuelta al home — utiles en cualquier otra pagina, una distraccion (y una
 * salida del flujo) justo antes de pagar. Aqui solo van los dos documentos
 * que el checkout ya exige aceptar arriba, para que su link tambien quede a
 * la vista sin sacar a nadie de la pagina.
 */
export function CheckoutFooter({ lang, footer, nav }: CheckoutFooterProps) {
  const empresas = useDeslindeEmpresas();
  return (
    <footer className="mx-auto max-w-[1440px] px-pagina py-10">
      <nav aria-label={footer.legalLabel} className="flex flex-wrap gap-x-6 gap-y-2">
        <Link
          href={hrefDeslinde(lang, empresas)}
          className="inline-flex min-h-11 items-center texto-cuerpo text-foreground underline underline-offset-4 transition-colors hover:text-cafe"
        >
          {footer.waiver}
        </Link>
        <Link
          href={`/${lang}/privacidad`}
          className="inline-flex min-h-11 items-center texto-cuerpo text-foreground underline underline-offset-4 transition-colors hover:text-cafe"
        >
          {footer.privacy}
        </Link>
      </nav>
      <p className="mt-2 texto-cuerpo text-foreground">
        {new Date().getFullYear()} {nav.brandMain} {nav.brandAccent}. {footer.rights}
      </p>
    </footer>
  );
}
