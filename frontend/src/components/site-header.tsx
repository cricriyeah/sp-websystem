'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Image from 'next/image';
import { List, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { getSedes } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { leerSedePreferidaCliente } from '@/lib/sede';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { LangSwitch } from '@/components/lang-switch';
import { SedeSelector } from '@/components/sede-selector';
import { ContinuarReservacion } from '@/components/continuar-reservacion';

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
  /**
   * Header de checkout: logo, idioma y WhatsApp, sin enlaces a la sede ni
   * selector de destino. Con dinero en juego cada salida extra es atención que
   * se fuga, y cambiar de destino a media compra puede tirar el pedido.
   */
  minimo?: boolean;
};

export function SiteHeader({
  lang,
  nav,
  continuar,
  variante = 'sede',
  sedeSlugActual,
  className = '',
  minimo = false,
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

  const brandMain = variante === 'hub' ? nav.brandMain : (sedeIndiceActiva?.empresaFundadoraNombre ?? nav.brandMain);
  const brandAccent = variante === 'hub' ? nav.brandAccent : '';
  const logoSrc =
    variante === 'hub' ? '/logos/wordmark-agencia.svg' : (sedeIndiceActiva?.logo ?? '/logos/wordmark-agencia.svg');

  const anclaBase = variante === 'sede' && slugActual ? hrefSede(lang, slugActual) : null;

  const links = minimo ? [] : anclaBase ? [
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
      <header className="relative mx-auto flex h-20 w-full items-center justify-between gap-4 border-b border-border bg-background px-6 sm:px-8 lg:h-20 lg:max-w-[1440px] lg:border lg:border-border lg:px-6 lg:shadow-[0_18px_45px_rgba(11,36,32,0.16)]">
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
            className="h-11 w-auto lg:h-14"
          />
        </Link>

        {links.length > 1 && (
          <nav className="hidden items-center gap-4 2xl:flex">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="whitespace-nowrap text-[13px] text-foreground transition-colors hover:text-accent"
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
          {minimo ? (
            // El idioma en escritorio ya lo da el selector fijo del layout (abajo a la izquierda):
            // repetirlo aquí lo duplicaba. En móvil sigue en el menú.
            <WhatsappContact nav={nav} tone="plain" />
          ) : (
            <>
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
            </>
          )}

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className={`flex h-11 w-11 items-center justify-center border border-border text-foreground ${minimo ? 'lg:hidden' : '2xl:hidden'}`}
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
              className={`absolute inset-x-0 top-full flex flex-col border-b border-border bg-surface px-6 py-2 shadow-[0_16px_40px_rgba(11,36,32,0.18)] sm:px-8 ${minimo ? 'lg:hidden' : '2xl:hidden'}`}
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
              {!minimo && (
                <div className="flex items-center justify-between border-b border-border-strong py-3.5">
                  <span className="text-[15px] text-muted">{nav.sedeLabel}</span>
                  <SedeSelector
                    lang={lang}
                    sedes={sedesDisponibles}
                    sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
                    placeholder={variante === 'hub' ? nav.eligeSede : undefined}
                    label={nav.sedeLabel}
                    variant="header"
                  />
                </div>
              )}
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
      {mostrarContinuar && continuar && (
        <div ref={bandaRef} className="mx-auto w-full lg:max-w-[1440px] lg:pt-2">
          <ContinuarReservacion lang={lang} dict={{ continuar }} />
        </div>
      )}
    </div>
  );
}
