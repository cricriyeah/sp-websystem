import Image from 'next/image';
import Link from 'next/link';
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
    <footer id="contacto" className="scroll-mt-24 overflow-hidden bg-tinta text-hero-ink">
      <div className="mx-auto max-w-[1440px] px-4 pt-20 sm:px-6 lg:px-12 lg:pt-24">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr] lg:gap-12">
          <div className="flex flex-col items-start gap-5">
            <h2 className="max-w-[13ch] texto-seccion">
              {footer.headline}
            </h2>
            <Link
              href={sedeSlug ? hrefSede(lang, sedeSlug, ANCLA_DE.reservar) : hrefInicio(lang, ANCLA_HUB.sedes)}
              className={botonClases({ variante: 'campana-claro' })}
            >
              {bookLabel}
            </Link>
          </div>

          {negocio && (
            <div className="flex flex-col gap-3">
              <span className="text-sm font-semibold text-cafe-bruma">{footer.addressLabel}</span>
              <span className="inline-flex min-h-11 items-center text-base">{negocio.calle}</span>
              <span className="text-base">
                {negocio.ciudad}, {negocio.estado}
              </span>
              <span className="mt-3 text-sm font-semibold text-cafe-bruma">{footer.hoursLabel}</span>
              <span className="inline-flex min-h-11 items-center text-base">{footer.hours}</span>
              <span className="mt-3 text-sm font-semibold text-cafe-bruma">{footer.officeLabel}</span>
              <span className="inline-flex min-h-11 items-center text-base">{footer.office}</span>
            </div>
          )}

          <nav aria-label={footer.exploreLabel} className="flex flex-col gap-3">
            <span className="text-sm font-semibold text-cafe-bruma">{footer.exploreLabel}</span>
            {secciones.map((link) => (
              // El mapa solo existe desde 1024 px.
              <Link key={link.href} href={link.href} className={`${link.href.endsWith(`#${ANCLA_HUB.mapa}`) ? 'hidden lg:inline-flex' : 'inline-flex'} min-h-11 items-center text-base transition-colors hover:text-cafe-claro`}>
                {link.label}
              </Link>
            ))}
          </nav>

          <nav aria-label={footer.legalLabel} className="flex flex-col gap-3">
            <span className="text-sm font-semibold text-cafe-bruma">{footer.legalLabel}</span>
            {legales.map((link) => (
              <Link key={link.href} href={link.href} className="inline-flex min-h-11 items-center text-base transition-colors hover:text-cafe-claro">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>

        {/* El logo completo, a todo el ancho y en blanco (el SVG es negro sin relleno propio). */}
        <Image
          src="/sunbajaexperience/logolg.svg"
          alt="Sun Baja Experience"
          width={286}
          height={91}
          sizes="(min-width: 1440px) 1344px, 100vw"
          className="mt-16 h-auto w-full invert lg:mt-24"
        />

        <div className="flex flex-col gap-2 pb-10 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm">
            Sun Baja Experience. {footer.rights}
          </span>
          {negocio && <span className="text-sm">{negocio.ciudad}, {negocio.estado}</span>}
        </div>
      </div>
    </footer>
  );
}
