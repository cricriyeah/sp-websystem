import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';

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
  return (
    <footer className="mx-auto max-w-6xl px-6 py-10 sm:px-8 lg:px-12">
      <nav aria-label={footer.legalLabel} className="flex flex-wrap gap-x-6 gap-y-2">
        <Link
          href={`/${lang}/deslinde`}
          className="text-sm text-muted transition-colors hover:text-foreground"
        >
          {footer.waiver}
        </Link>
        <Link
          href={`/${lang}/privacidad`}
          className="text-sm text-muted transition-colors hover:text-foreground"
        >
          {footer.privacy}
        </Link>
      </nav>
      <p className="mt-4 text-sm text-muted">
        {new Date().getFullYear()} {nav.brandMain} {nav.brandAccent}. {footer.rights}
      </p>
    </footer>
  );
}
