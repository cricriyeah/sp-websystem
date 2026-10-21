import Image from 'next/image';
import Link from 'next/link';
import { Money, WhatsappLogo } from '@phosphor-icons/react/ssr';
import { botonClases } from '@/components/ui/variantes';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';
import { tieneWhatsapp, whatsappHref, whatsappVisible } from '@/lib/contacto';
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

const FORMAS_DE_PAGO = [
  { nombre: 'Visa', src: '/pagos/visa.svg' },
  { nombre: 'Mastercard', src: '/pagos/mastercard.svg' },
  { nombre: 'American Express', src: '/pagos/amex.svg' },
] as const;

const TITULO_GRUPO = 'texto-etiqueta text-cafe-bruma';
const ENLACE = 'inline-flex min-h-11 items-center texto-cuerpo transition-colors hover:text-cafe-claro';

/**
 * Pie del sitio (F10), con el logo gigante al final. Cuatro grupos, uno por la pregunta con la que llega
 * el visitante: dónde reservo (el titular, el botón y las secciones de la sede), con quién hablo (el
 * número de atención al cliente, la oficina, el punto de encuentro y los horarios), cómo pago (las
 * tarjetas y el efectivo) y qué dice lo legal.
 */
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
        <div className="grid gap-14 sm:grid-cols-2 lg:grid-cols-[1.5fr_1.1fr_1fr_0.8fr] lg:gap-12">
          <div className="flex flex-col items-start gap-6">
            <h2 className="max-w-[24ch] texto-paso">{footer.headline}</h2>
            <Link
              href={sedeSlug ? hrefSede(lang, sedeSlug, ANCLA_DE.reservar) : hrefInicio(lang, ANCLA_HUB.sedes)}
              className={botonClases({ variante: 'campana-claro' })}
            >
              {bookLabel}
            </Link>
            <nav aria-label={footer.exploreLabel}>
              <ul className="flex flex-wrap gap-x-6">
                {secciones.map((link) => (
                  // El mapa solo existe desde 1024 px.
                  <li key={link.href} className={link.href.endsWith(`#${ANCLA_HUB.mapa}`) ? 'hidden lg:block' : undefined}>
                    <Link href={link.href} className={ENLACE}>{link.label}</Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>

          <div className="flex flex-col items-start gap-3">
            <h3 className={TITULO_GRUPO}>{footer.officeLabel}</h3>
            {tieneWhatsapp && (
              <a
                href={whatsappHref(nav.whatsappMessage)}
                target="_blank"
                rel="noopener"
                aria-label={`${nav.whatsappCta}: ${whatsappVisible()}`}
                className={botonClases({ variante: 'campana-claro' })}
              >
                <WhatsappLogo size={20} weight="fill" aria-hidden="true" />
                {whatsappVisible()}
              </a>
            )}
            <p className="mt-2 texto-cuerpo">{footer.office}</p>
            {negocio && (
              <>
                <p className="mt-4 texto-etiqueta text-cafe-bruma">{footer.addressLabel}</p>
                <p className="texto-cuerpo">
                  {negocio.calle}
                  <br />
                  {negocio.ciudad}, {negocio.estado}
                </p>
                <p className="mt-4 texto-etiqueta text-cafe-bruma">{footer.hoursLabel}</p>
                <p className="texto-cuerpo">{footer.hours}</p>
              </>
            )}
          </div>

          <div className="flex flex-col items-start gap-3">
            <h3 className={TITULO_GRUPO}>{footer.pagosLabel}</h3>
            <ul className="flex flex-wrap items-center gap-3">
              {FORMAS_DE_PAGO.map((forma) => (
                <li key={forma.nombre}>
                  <Image src={forma.src} alt={forma.nombre} width={48} height={32} className="h-8 w-12" />
                </li>
              ))}
              <li className="inline-flex h-8 items-center gap-2 rounded-full bg-white px-3 texto-pie font-semibold text-tinta">
                <Money size={18} aria-hidden="true" />
                {footer.pagosEfectivoCorto}
              </li>
            </ul>
            <p className="max-w-[28ch] texto-cuerpo">
              {footer.pagosTarjetas}. {footer.pagosEfectivo}.
            </p>
          </div>

          <nav aria-label={footer.legalLabel} className="flex flex-col items-start gap-1">
            <h3 className={`${TITULO_GRUPO} mb-2`}>{footer.legalLabel}</h3>
            {legales.map((link) => (
              <Link key={link.href} href={link.href} className={ENLACE}>
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
          <span className="texto-cuerpo">
            Sun Baja Experience. {footer.rights}
          </span>
          <span className="texto-cuerpo">{footer.credito}</span>
        </div>
      </div>
    </footer>
  );
}
