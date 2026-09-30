import Link from 'next/link';
import Image from 'next/image';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';

type SiteFooterProps = {
  lang: Locale;
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
  bookLabel: string;
  /** `null` en el hub y en cualquier sede sin `negocio`: el bloque de dirección/horario se omite en vez de mostrar el de otra sede. */
  negocio: SedeNegocio;
  sedeSlug?: string;
};

export function SiteFooter({ lang, footer, nav, bookLabel, negocio, sedeSlug }: SiteFooterProps) {
  const baseSede = sedeSlug ? `/${lang}/sede/${sedeSlug}` : null;
  const es = lang === 'es';
  const secciones = baseSede ? [
    { href: baseSede + '#nosotros', label: nav.nosotros },
    { href: baseSede + '#experiencias', label: es ? 'Experiencias y paquetes' : 'Experiences and packages' },
    { href: baseSede + '#servicios', label: es ? 'Servicios' : 'Services' },
    { href: baseSede + '#temporadas', label: nav.temporadas },
    { href: baseSede + '#galeria', label: nav.galeria },
    { href: baseSede + '#resenas', label: es ? 'Opiniones' : 'Reviews' },
    { href: baseSede + '#preguntas', label: 'FAQs' },
  ] : [
    { href: '/' + lang + '#hub-mapa-destinos', label: es ? 'Mapa' : 'Map' },
    { href: '/' + lang + '#sedes', label: es ? 'Sedes' : 'Destinations' },
    { href: '/' + lang + '#nosotros', label: nav.nosotros },
    { href: '/' + lang + '#colaboradores', label: es ? 'Colaboradores' : 'Partners' },
  ];

  const legales = [
    { href: `/${lang}/deslinde`, label: footer.waiver },
    { href: `/${lang}/privacidad`, label: footer.privacy },
  ];

  return (
    <footer
      id="contacto"
      className="relative scroll-mt-24 overflow-hidden border-t border-border bg-background"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'radial-gradient(50% 60% at 88% 0%, rgba(49,28,153,0.10), transparent 70%)',
        }}
      />
      <div className="relative mx-auto max-w-6xl px-6 pt-20 sm:px-8 lg:px-12 lg:pt-24">
        <div className="grid gap-10 pb-16 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr] lg:gap-12">
          <div className="flex flex-col items-start gap-5">
            <h2 className="max-w-[13ch] text-3xl leading-[1.05] text-foreground lg:text-[38px]">
              {footer.headline}
            </h2>
            <Link
              href={sedeSlug === 'la-paz' ? `/${lang}/reservar` : baseSede ? `${baseSede}#experiencias` : `/${lang}#sedes`}
              className="inline-flex items-center rounded-full bg-foreground px-6 py-3 text-sm font-semibold text-background transition-transform active:scale-[0.98]"
            >
              {bookLabel}
            </Link>
          </div>

          {negocio && (
            <div className="flex flex-col gap-3">
              <span className="text-xs font-semibold text-muted">{footer.addressLabel}</span>
              <span className="text-base text-foreground">{negocio.calle}</span>
              <span className="text-base text-muted">
                {negocio.ciudad}, {negocio.estado}
              </span>
              <span className="mt-3 text-xs font-semibold text-muted">{footer.hoursLabel}</span>
              <span className="text-base text-foreground">{footer.hours}</span>
              <span className="mt-3 text-xs font-semibold text-muted">{footer.officeLabel}</span>
              <span className="text-base text-foreground">{footer.office}</span>
            </div>
          )}

          <nav aria-label={footer.exploreLabel} className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-muted">{footer.exploreLabel}</span>
            {secciones.map((link) => (
              <Link key={link.href} href={link.href} className="text-base text-foreground">
                {link.label}
              </Link>
            ))}
          </nav>

          <nav aria-label={footer.legalLabel} className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-muted">{footer.legalLabel}</span>
            {legales.map((link) => (
              <Link key={link.href} href={link.href} className="text-base text-foreground">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="relative mx-auto max-w-6xl overflow-hidden px-6 pb-10 sm:px-8 lg:px-12">
        <Image
          src={sedeSlug === 'la-paz' ? '/logos/svglogosalysol2.svg' : '/logos/wordmark-agencia.svg'}
          alt=""
          width={261}
          height={123}
          sizes="100vw"
          className="mx-auto h-auto w-full max-w-[922px]"
        />
        <div className="mt-8 flex flex-col gap-2 border-t border-border-strong pt-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted">
            Sal y Sol Baja Experiences. {footer.rights}
          </span>
          {negocio && <span className="text-sm text-muted">{negocio.ciudad}, {negocio.estado}</span>}
        </div>
      </div>
    </footer>
  );
}
