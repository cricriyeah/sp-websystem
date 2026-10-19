'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Image from 'next/image';
import { List, X } from '@phosphor-icons/react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { marcaDe } from '@/content/empresas-marca';
import { SEDES_INDICE } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { getSedes } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { leerSedePreferidaCliente } from '@/lib/sede';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { SelectorIdioma } from '@/components/selector-idioma';
import { SedeSelector } from '@/components/sede-selector';
import { ContinuarReservacion } from '@/components/continuar-reservacion';
import { Button } from '@/components/ui/button';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
  continuar?: Dictionary['continuar'];
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
  continuar,
  variante = 'sede',
  sedeSlugActual,
  className = '',
}: SiteHeaderProps) {
  const pathname = usePathname();
  // La banda va en todo el sitio (hub y sedes), salvo dentro del checkout, donde el propio
  // checkout ya retoma la reserva y el aviso sobraria.
  const mostrarContinuar = !/^\/(?:es|en)\/(?:reservar|traslados)(?:\/|$)/.test(pathname);
  const [open, setOpen] = useState(false);
  const bandaRef = useRef<HTMLDivElement>(null);
  const sinMovimiento = useReducedMotion();
  const [slugResuelto, setSlugResuelto] = useState<string | undefined>(sedeSlugActual);
  const [sedesDisponibles, setSedesDisponibles] = useState<SedeIndiceEntry[]>(Object.values(SEDES_INDICE));
  // El header es `fixed` y las paginas se apartan con `--nav-alto`: la banda le suma su
  // propia altura a traves de `--banda-alto` (ver globals.css), asi todo el contenido baja
  // solo, sin que cada pagina sepa que existe. Sin banda vale 0 y nada cambia.
  useEffect(() => {
    const banda = bandaRef.current;
    if (!banda) return;
    const raiz = document.documentElement;
    const medir = () => raiz.style.setProperty('--banda-alto', `${banda.getBoundingClientRect().height}px`);
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(banda);
    return () => { observador.disconnect(); raiz.style.removeProperty('--banda-alto'); };
  }, [mostrarContinuar]);
  useEffect(() => {
    let montado = true;
    getSedes().catch(() => null).then(data => {
      if (!montado) return;
      const activas = sedesActivas(SEDES_INDICE, data);
      setSedesDisponibles(activas);
      if (variante === 'hub' || sedeSlugActual) return;
      const enUrl = new URLSearchParams(window.location.search).get('sede');
      const preferida = leerSedePreferidaCliente();
      setSlugResuelto([enUrl, preferida].find(slug => slug && activas.some(s => s.slug === slug)) ?? undefined);
    });
    return () => { montado = false; };
  }, [pathname, sedeSlugActual, variante]);

  const slugActual = sedeSlugActual ?? slugResuelto ?? sedesDisponibles[0]?.slug;
  const sedeIndiceActiva: SedeIndiceEntry | undefined =
    variante === 'sede' && slugActual ? SEDES_INDICE[slugActual] : undefined;

  const protagonista = marcaDe(sedeIndiceActiva?.empresaProtagonistaSlug);
  const brandMain = variante === 'hub' ? nav.brandMain : (protagonista?.nombre ?? nav.brandMain);
  const brandAccent = variante === 'hub' ? nav.brandAccent : '';
  const logoSrc =
    variante === 'hub' ? '/logos/wordmark-agencia.svg' : (protagonista?.logo ?? '/logos/wordmark-agencia.svg');

  const anclaBase = variante === 'sede' && slugActual ? hrefSede(lang, slugActual) : null;

  const links = anclaBase ? [
    { href: anclaBase + '#nosotros', label: nav.nosotros },
    { href: anclaBase + '#experiencias', label: nav.experiencias },
    { href: anclaBase + '#servicios', label: nav.servicios },
    { href: anclaBase + '#temporadas', label: nav.temporadas },
    { href: anclaBase + '#galeria', label: nav.galeria },
    { href: anclaBase + '#resenas', label: nav.opiniones },
    { href: anclaBase + '#preguntas', label: 'FAQs' },
  ] : [
    { href: hrefInicio(lang, 'hub-mapa-destinos'), label: nav.mapa },
    { href: hrefInicio(lang, 'sedes'), label: nav.sedes },
    { href: hrefInicio(lang, 'nosotros'), label: nav.nosotros },
    { href: hrefInicio(lang, 'colaboradores'), label: nav.colaboradores },
  ];

  return (
    <div className={`fixed inset-x-0 top-0 z-40 lg:top-4 lg:px-8 ${className}`}>
      <header className="relative mx-auto flex h-16 w-full items-center justify-between gap-4 border-b border-border bg-arena/95 px-4 backdrop-blur sm:px-6 lg:max-w-[1440px] lg:rounded-card lg:border lg:border-border lg:px-6">
        <Link
          href={hrefInicio(lang)}
          className="flex shrink-0 items-center text-foreground"
          onClick={() => setOpen(false)}
        >
          <Image
            src={logoSrc}
            alt={`${brandMain} ${brandAccent}`.trim()}
            width={1026}
            height={331}
            priority
            className="h-10 w-auto lg:h-12"
          />
        </Link>

        {links.length > 1 && (
          <nav className="hidden items-center gap-4 xl:flex">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="inline-flex min-h-11 items-center whitespace-nowrap text-sm text-foreground transition-colors hover:text-accent"
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
              className="hidden min-h-11 items-center text-base text-foreground transition-colors hover:text-accent lg:inline-flex"
            >
              {links[0].label}
            </Link>
          )}
          <SelectorIdioma lang={lang} label={nav.switchLang} />
          {/* En móvil el idioma vive en el menú; desde lg va en la cabecera (arriba). */}
          <SedeSelector
            lang={lang}
            sedes={sedesDisponibles}
            sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
            placeholder={variante === 'hub' ? nav.eligeSede : undefined}
            label={nav.sedeLabel}
            variant="header"
            className="hidden sm:inline-block"
          />
          <div className="hidden xl:block"><WhatsappContact nav={nav} tone="plain" /></div>

          <Button
            variante="libre"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className={`flex h-11 w-11 items-center justify-center border border-border rounded-control text-foreground xl:hidden`}
          >
            {open ? <X size={18} /> : <List size={18} />}
          </Button>
        </div>

        <AnimatePresence>
          {open && (
            <m.div
              key="menu-movil"
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className={`absolute inset-x-0 top-full flex flex-col rounded-b-card border border-t-0 border-border bg-arena px-4 py-2 shadow-n2 sm:px-6 lg:mt-2 lg:rounded-card lg:border-t xl:hidden`}
            >
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="border-b border-border-strong flex min-h-11 items-center py-2 text-base text-foreground last:border-b-0"
                >
                  {link.label}
                </Link>
              ))}
              <div className="flex items-center justify-between border-b border-border-strong py-3.5">
                <span className="text-base text-muted">{nav.sedeLabel}</span>
                <SedeSelector
                  lang={lang}
                  sedes={sedesDisponibles}
                  sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
                  placeholder={variante === 'hub' ? nav.eligeSede : undefined}
                  label={nav.sedeLabel}
                  variant="header"
                />
              </div>
              <div className="py-3">
                <WhatsappContact nav={nav} variant="menu" />
              </div>
            </m.div>
          )}
        </AnimatePresence>
      </header>
      {mostrarContinuar && continuar && (
        <div ref={bandaRef} className="mx-auto w-full lg:max-w-[1440px] lg:pt-2">
          <ContinuarReservacion lang={lang} dict={{ continuar }} />
        </div>
      )}
    </div>
  );
}
