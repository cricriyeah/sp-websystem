import Link from 'next/link';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { botonClases } from '@/components/ui/variantes';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { ANCLA_DE, ANCLA_HUB } from '@/lib/secciones-sede';

type SiteFooterProps = {
  lang: Locale;
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
  bookLabel: string;
  /** `null` en el hub y en cualquier sede sin `negocio`: el bloque de dirección/horario se omite en vez de mostrar el de otra sede. */
  negocio: SedeNegocio;
  sedeSlug?: string;
  /** El menú de la sede (ver `SiteHeader`). Sin él, una página de sede lleva solo «Reservar». */
  anclas?: { ancla: string; etiqueta: string }[];
};

export function SiteFooter({ lang, footer, nav, bookLabel, negocio, sedeSlug, anclas }: SiteFooterProps) {
  const baseSede = sedeSlug ? hrefSede(lang, sedeSlug) : null;
  const secciones = baseSede
    ? (anclas?.length ? anclas.map((a) => ({ href: baseSede + a.ancla, label: a.etiqueta })) : [{ href: baseSede, label: nav.reservar }])
    : [
        { href: hrefInicio(lang, ANCLA_HUB.mapa), label: nav.mapa },
        { href: hrefInicio(lang, ANCLA_HUB.sedes), label: nav.sedes },
        { href: hrefInicio(lang, ANCLA_HUB.comoFunciona), label: nav.comoFunciona },
        { href: hrefInicio(lang, ANCLA_HUB.empresas), label: nav.empresas },
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
          background: 'var(--tinte-cafe-pie)',
        }}
      />
      <div className="relative mx-auto max-w-6xl px-6 pt-20 sm:px-8 lg:px-12 lg:pt-24">
        <div className="grid gap-10 pb-16 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr] lg:gap-12">
          <div className="flex flex-col items-start gap-5">
            <EmpresaSello nombre="Sun Baja Experience" tamano={64} />
            <h2 className="max-w-[13ch] texto-seccion text-foreground">
              {footer.headline}
            </h2>
            <Link
              href={sedeSlug === 'la-paz' ? `/${lang}/reservar` : sedeSlug ? hrefSede(lang, sedeSlug, ANCLA_DE.reservar) : hrefInicio(lang, ANCLA_HUB.sedes)}
              className={botonClases({ variante: 'principal' })}
            >
              {bookLabel}
            </Link>
          </div>

          {negocio && (
            <div className="flex flex-col gap-3">
              <span className="text-sm font-semibold text-muted">{footer.addressLabel}</span>
              <span className="inline-flex min-h-11 items-center text-base text-foreground">{negocio.calle}</span>
              <span className="text-base text-muted">
                {negocio.ciudad}, {negocio.estado}
              </span>
              <span className="mt-3 text-xs font-semibold text-muted">{footer.hoursLabel}</span>
              <span className="inline-flex min-h-11 items-center text-base text-foreground">{footer.hours}</span>
              <span className="mt-3 text-xs font-semibold text-muted">{footer.officeLabel}</span>
              <span className="inline-flex min-h-11 items-center text-base text-foreground">{footer.office}</span>
            </div>
          )}

          <nav aria-label={footer.exploreLabel} className="flex flex-col gap-3">
            <span className="text-sm font-semibold text-muted">{footer.exploreLabel}</span>
            {secciones.map((link) => (
              // El mapa solo existe desde 1024 px.
              <Link key={link.href} href={link.href} className={`${link.href.endsWith(`#${ANCLA_HUB.mapa}`) ? 'hidden lg:inline-flex' : 'inline-flex'} min-h-11 items-center text-base text-foreground`}>
                {link.label}
              </Link>
            ))}
          </nav>

          <nav aria-label={footer.legalLabel} className="flex flex-col gap-3">
            <span className="text-sm font-semibold text-muted">{footer.legalLabel}</span>
            {legales.map((link) => (
              <Link key={link.href} href={link.href} className="inline-flex min-h-11 items-center text-base text-foreground">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="relative mx-auto max-w-6xl px-6 pb-10 sm:px-8 lg:px-12">
        <div className="flex flex-col gap-2 border-t border-border-strong pt-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted">
            Sun Baja Experience. {footer.rights}
          </span>
          {negocio && <span className="text-sm text-muted">{negocio.ciudad}, {negocio.estado}</span>}
        </div>
      </div>
    </footer>
  );
}
