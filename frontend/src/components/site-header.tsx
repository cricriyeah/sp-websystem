'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Image from 'next/image';
import { List, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { getSedes } from '@/lib/api';
import { leerSedePreferidaCliente } from '@/lib/sede';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { LangSwitch } from '@/components/lang-switch';
import { SedeSelector } from '@/components/sede-selector';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
  /** 'hub' solo en `/[lang]`. Cualquier otra pagina (con o sin sede propia) usa 'sede'. */
  variante?: 'hub' | 'sede';
  /** Si no llega, se resuelve en cliente (query, localStorage/cookie, o primera sede activa). */
  sedeSlugActual?: string;
  /** Clases extra del `<header>`. Existe para el `print:hidden` del recibo. */
  className?: string;
};

export function SiteHeader({
  lang,
  nav,
  variante = 'sede',
  sedeSlugActual,
  className = '',
}: SiteHeaderProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const sinMovimiento = useReducedMotion();
  const [slugResuelto, setSlugResuelto] = useState<string | undefined>(sedeSlugActual);
  // Fallo abierto desde el primer render (sin esperar la red): todas las
  // sedes del indice. `sedesActivas` reduce esta lista cuando `getSedes()`
  // resuelve. `SedeSelector` recibe esta misma lista por prop — nunca vuelve
  // a pedir `getSedes()` por su cuenta (arch-critic ronda 2, hallazgo 5).
  const [sedesDisponibles, setSedesDisponibles] = useState<SedeIndiceEntry[]>(
    Object.values(SEDES_INDICE),
  );

  // Sin slug explicito, la sede activa se resuelve en cliente
  // (localStorage/cookie) post-hidratacion. Un crawler ve el fallback
  // (primera sede activa), nunca un valor en blanco.
  useEffect(() => {
    let montado = true;
    getSedes()
      .then((data) => data, () => null)
      .then((sedesApi) => {
        if (!montado) return;
        const activas = sedesActivas(SEDES_INDICE, sedesApi);
        setSedesDisponibles(activas);
        if (sedeSlugActual) return;
        const enUrl = new URLSearchParams(window.location.search).get('sede');
        const preferida = leerSedePreferidaCliente();
        setSlugResuelto(
          [enUrl, preferida].find((slug) => slug && activas.some((s) => s.slug === slug))
            ?? activas[0]?.slug,
        );
      });
    return () => {
      montado = false;
    };
  }, [pathname, sedeSlugActual]);

  const slugActual = sedeSlugActual ?? slugResuelto ?? sedesDisponibles[0]?.slug;
  const sedeIndiceActiva: SedeIndiceEntry | undefined =
    variante === 'sede' && slugActual ? SEDES_INDICE[slugActual] : undefined;

  const brandMain = variante === 'hub' ? nav.brandMain : (sedeIndiceActiva?.empresaFundadoraNombre ?? nav.brandMain);
  const brandAccent = variante === 'hub' ? nav.brandAccent : '';
  const logoSrc =
    variante === 'hub' ? '/logos/wordmark-agencia.svg' : (sedeIndiceActiva?.logo ?? '/logos/wordmark-agencia.svg');

  const anclaBase = variante === 'sede' && slugActual ? `/${lang}/sede/${slugActual}` : null;

  const links = anclaBase
    ? [
        { href: `${anclaBase}#experiencias`, label: nav.catalogo },
        { href: `${anclaBase}#nosotros`, label: nav.nosotros },
        ...(slugActual === 'la-paz' ? [
          { href: `${anclaBase}#temporadas`, label: nav.temporadas },
          { href: `${anclaBase}#galeria`, label: nav.galeria },
          { href: `${anclaBase}#preguntas`, label: nav.preguntas },
        ] : []),
      ]
    : [{ href: `/${lang}#sedes`, label: nav.catalogo }];

  return (
    <div className={`fixed inset-x-0 top-0 z-40 lg:top-4 lg:px-8 ${className}`}>
      <header className="relative mx-auto flex h-20 w-full items-center justify-between gap-6 border-b border-border bg-background px-6 sm:px-8 lg:h-[88px] lg:max-w-6xl lg:border lg:border-border lg:px-12 lg:shadow-[0_18px_45px_rgba(11,36,32,0.16)]">
        <Link
          href={`/${lang}`}
          className="flex shrink-0 items-center text-foreground"
          onClick={() => setOpen(false)}
        >
          <Image
            src={logoSrc}
            alt={`${brandMain} ${brandAccent}`.trim()}
            width={1026}
            height={331}
            priority
            className="h-11 w-auto lg:h-14"
          />
        </Link>

        {/* En el hub `links` trae un solo item (spec §5: nada de nosotros/
            temporadas/galeria/preguntas ahi) — con `justify-between` de 3 hijos
            un solo link queda flotando solo en medio de un hueco enorme, se lee
            roto (hallazgo del dueño, 2026-09-16). Con 1 item se pliega al
            cluster derecho, junto al selector; con 2+ (cualquier sede) conserva
            su fila propia centrada, que ahi si tiene peso visual. */}
        {links.length > 1 && (
          <nav className="hidden items-center gap-7 lg:flex">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-[15px] text-foreground transition-colors hover:text-accent"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="flex items-center gap-3">
          {links.length === 1 && (
            <Link
              href={links[0].href}
              className="hidden text-[15px] text-foreground transition-colors hover:text-accent lg:inline-flex"
            >
              {links[0].label}
            </Link>
          )}
          <SedeSelector
            lang={lang}
            sedes={sedesDisponibles}
            sedeSeleccionadaSlug={slugActual}
            label={nav.sedeLabel}
            variant="header"
            className="hidden sm:inline-block"
          />
          <WhatsappContact nav={nav} tone="plain" />

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className="flex h-11 w-11 items-center justify-center border border-border text-foreground lg:hidden"
          >
            {open ? <X size={18} /> : <List size={18} />}
          </button>
        </div>

        <AnimatePresence>
          {open && (
            <motion.div
              key="menu-movil"
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="absolute inset-x-0 top-full flex flex-col border-b border-border bg-surface px-6 py-2 shadow-[0_16px_40px_rgba(11,36,32,0.18)] sm:px-8 lg:hidden"
            >
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="border-b border-border-strong py-3.5 text-[15px] text-foreground last:border-b-0"
                >
                  {link.label}
                </Link>
              ))}
              <div className="flex items-center justify-between border-b border-border-strong py-3.5">
                <span className="text-[15px] text-muted">{nav.sedeLabel}</span>
                <SedeSelector
                  lang={lang}
                  sedes={sedesDisponibles}
                  sedeSeleccionadaSlug={slugActual}
                  label={nav.sedeLabel}
                  variant="header"
                />
              </div>
              <div className="flex items-center justify-between border-b border-border-strong py-3.5">
                <span className="text-[15px] text-muted">{nav.switchLang}</span>
                <LangSwitch lang={lang} label={nav.switchLang} placement="bottom" align="right" />
              </div>
              <div className="py-3">
                <WhatsappContact nav={nav} variant="menu" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>
    </div>
  );
}
