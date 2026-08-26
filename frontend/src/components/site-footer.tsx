import Link from 'next/link';
import Image from 'next/image';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';

type SiteFooterProps = {
  lang: Locale;
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
  bookLabel: string;
};

/**
 * Una sola fila de 4 columnas a sangre, no dos filas dentro de un contenedor
 * centrado: titular+CTA, punto de encuentro/salidas, el mapa del sitio, legal.
 * La barra de derechos va aparte, con su propio borde arriba.
 *
 * Va sobre papel blanco, no sobre bruma. Lo que lo separa de la seccion que
 * viene encima es la linea de `border-t`, no un cambio de fondo.
 */
export function SiteFooter({ lang, footer, nav, bookLabel }: SiteFooterProps) {
  const secciones = [
    { href: `/${lang}#nosotros`, label: nav.nosotros },
    { href: `/${lang}#temporadas`, label: nav.temporadas },
    { href: `/${lang}#incluye`, label: nav.contacto },
    { href: `/${lang}#preguntas`, label: nav.preguntas },
  ];

  const legales = [
    { href: `/${lang}/deslinde`, label: footer.waiver },
    { href: `/${lang}/privacidad`, label: footer.privacy },
  ];

  return (
    <footer
      id="contacto"
      className="relative scroll-mt-20 overflow-hidden border-t border-border bg-background"
    >
      {/* Mismo tratamiento que resenas: radial apagado con el indigo de la
          marca, no un degradado parejo de banco de imagenes. Aqui va arriba a
          la derecha para no pelear con el titular, que empieza a la izquierda. */}
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
              href={`/${lang}/reservar`}
              className="inline-flex items-center rounded-full bg-foreground px-6 py-3 text-sm font-semibold text-background transition-transform active:scale-[0.98]"
            >
              {bookLabel}
            </Link>
          </div>

          <div className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-muted">{footer.addressLabel}</span>
            <span className="text-base text-foreground">{footer.address}</span>
            <span className="text-base text-muted">{footer.city}</span>
            <span className="mt-3 text-xs font-semibold text-muted">{footer.hoursLabel}</span>
            <span className="text-base text-foreground">{footer.hours}</span>
          </div>

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

        <div className="flex flex-col gap-2 border-t border-border-strong py-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted">
            {nav.brandMain} {nav.brandAccent}. {footer.rights}
          </span>
          <span className="text-sm text-muted">{nav.location}</span>
        </div>
      </div>

      {/* La marca a lo ancho, cerrando la pagina. Es el ultimo golpe de vista y
          por eso va sin contenedor: se alinea con el borde de la ventana, no con
          la reja de 1152px del resto del pie.

          `alt=""` porque no aporta nada nuevo a quien no la ve — el nombre ya
          esta escrito dos renglones arriba, en la linea de derechos. */}
      <div className="relative mx-auto max-w-6xl overflow-hidden px-6 pb-10 sm:px-8 lg:px-12">
        <Image
          src="/logos/svglogosalysol2.svg"
          alt=""
          width={261}
          height={123}
          sizes="100vw"
          // 922px: el ancho del contenido (1152) menos un 20%. Con `w-full`
          // debajo, en pantallas mas angostas sigue ocupando lo que haya.
          className="mx-auto h-auto w-full max-w-[922px]"
        />
      </div>
    </footer>
  );
}
