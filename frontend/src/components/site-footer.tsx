import Link from 'next/link';
import { MapPin, Anchor } from '@phosphor-icons/react/ssr';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';

type SiteFooterProps = {
  lang: Locale;
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
  bookLabel: string;
};

export function SiteFooter({ lang, footer, nav, bookLabel }: SiteFooterProps) {
  // Enlaces internos: desde el pie se llega a todo el sitio. Ayuda a quien
  // termino de leer y no quiere volver a subir, y le da a Google el mapa de
  // como se relacionan las paginas entre si.
  const secciones = [
    { href: `/${lang}#nosotros`, label: nav.nosotros },
    { href: `/${lang}#flota`, label: nav.flota },
    { href: `/${lang}#temporadas`, label: nav.temporadas },
    { href: `/${lang}#incluye`, label: nav.contacto },
    { href: `/${lang}#preguntas`, label: nav.preguntas },
  ];

  const legales = [
    { href: `/${lang}/deslinde`, label: footer.waiver },
    { href: `/${lang}/privacidad`, label: footer.privacy },
  ];

  return (
    <footer id="contacto" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <div className="flex flex-col gap-10 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
              {footer.headline}
            </h2>

            <div className="mt-8 flex flex-col gap-6 sm:flex-row sm:gap-14">
              <div className="flex gap-3">
                <MapPin size={20} className="mt-0.5 shrink-0 text-accent" />
                <div>
                  <p className="text-sm text-muted">{footer.addressLabel}</p>
                  <p className="mt-1 text-base text-foreground">{footer.address}</p>
                  <p className="text-base text-foreground">{footer.city}</p>
                </div>
              </div>

              <div className="flex gap-3">
                <Anchor size={20} className="mt-0.5 shrink-0 text-accent" />
                <div>
                  <p className="text-sm text-muted">{footer.hoursLabel}</p>
                  <p className="mt-1 text-base text-foreground">{footer.hours}</p>
                </div>
              </div>
            </div>
          </div>

          <Link
            href={`/${lang}/reservar`}
            className="inline-flex shrink-0 items-center justify-center rounded-full bg-accent px-8 py-4 text-sm font-medium text-accent-foreground transition-transform active:scale-[0.98]"
          >
            {bookLabel}
          </Link>
        </div>

        <div className="mt-16 grid gap-10 border-t border-border pt-10 sm:grid-cols-2 lg:grid-cols-4">
          <nav aria-label={footer.exploreLabel}>
            <p className="text-sm font-medium text-foreground">{footer.exploreLabel}</p>
            <ul className="mt-4 flex flex-col gap-2">
              {secciones.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label={footer.legalLabel}>
            <p className="text-sm font-medium text-foreground">{footer.legalLabel}</p>
            <ul className="mt-4 flex flex-col gap-2">
              {legales.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <p className="mt-12 text-sm text-muted">
          {new Date().getFullYear()} {nav.brandMain} {nav.brandAccent}. {footer.rights}
        </p>
      </div>
    </footer>
  );
}
