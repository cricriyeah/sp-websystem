'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { List, X } from '@phosphor-icons/react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { getSedes } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { leerSedePreferidaCliente } from '@/lib/sede';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { ANCLA_HUB } from '@/lib/secciones-sede';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { SelectorIdioma } from '@/components/selector-idioma';
import { SedeSelector } from '@/components/sede-selector';
import { ContinuarReservacion } from '@/components/continuar-reservacion';
import { Button } from '@/components/ui/button';
import { EmpresaSello } from '@/components/ui/empresa-sello';

const MARCA = 'Sun Baja Experience';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
  continuar?: Dictionary['continuar'];
  /** 'hub' solo en `/[lang]`. Cualquier otra pagina (con o sin sede propia) usa 'sede'. */
  variante?: 'hub' | 'sede';
  /** Si no llega, se resuelve en cliente (query, localStorage/cookie, o primera sede activa). */
  sedeSlugActual?: string;
  /**
   * La empresa protagonista de la sede: su sello va junto a nuestra marca. Solo la pasa la
   * página de sede; fuera de una sede (hub, servicio, legales) va solo la nuestra.
   */
  marcaSede?: { nombre: string; logo?: string };
  /**
   * El menú de la sede, armado por su página con `enlacesDeSede(seccionesDeSede(...))`: solo
   * las secciones que de verdad se pintan. Sin él, una página de sede lleva solo «Reservar».
   */
  anclas?: { ancla: string; etiqueta: string }[];
  /** Clases extra del `<header>`. Existe para el `print:hidden` del recibo. */
  className?: string;
};

export function SiteHeader({
  lang,
  nav,
  continuar,
  variante = 'sede',
  sedeSlugActual,
  marcaSede,
  anclas,
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
  const baseSede = variante === 'sede' && slugActual ? hrefSede(lang, slugActual) : null;

  const links = baseSede
    ? (anclas ?? []).map((a) => ({ href: baseSede + a.ancla, label: a.etiqueta }))
    : [
        { href: hrefInicio(lang, ANCLA_HUB.mapa), label: nav.mapa },
        { href: hrefInicio(lang, ANCLA_HUB.sedes), label: nav.sedes },
        { href: hrefInicio(lang, ANCLA_HUB.comoFunciona), label: nav.comoFunciona },
        { href: hrefInicio(lang, ANCLA_HUB.empresas), label: nav.empresas },
      ];
  if (baseSede && links.length === 0) links.push({ href: baseSede, label: nav.reservar });

  return (
    <div className={`fixed inset-x-0 top-0 z-40 lg:top-4 lg:px-8 ${className}`}>
      <header className="relative mx-auto flex h-16 w-full items-center justify-between gap-4 bg-superficie px-4 shadow-tarjeta sm:px-6 lg:max-w-[1440px] lg:rounded-full lg:px-6 lg:shadow-n2">
        <div className="flex shrink-0 items-center gap-3">
          <Link
            href={hrefInicio(lang)}
            className="flex items-center text-foreground"
            onClick={() => setOpen(false)}
          >
            {/* Nuestra marca es el monograma «SB» en todas las páginas (sin wordmark de texto). */}
            <EmpresaSello nombre={MARCA} tamano={32} />
          </Link>
          {marcaSede && (
            <EmpresaSello nombre={marcaSede.nombre} logo={marcaSede.logo} tamano={32} />
          )}
        </div>

        {links.length > 1 && (
          <nav className="hidden items-center gap-4 xl:flex">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="inline-flex min-h-11 items-center whitespace-nowrap texto-cuerpo transition-colors hover:text-cafe"
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
              className="hidden min-h-11 items-center texto-cuerpo transition-colors hover:text-cafe lg:inline-flex"
            >
              {links[0].label}
            </Link>
          )}
          <SelectorIdioma lang={lang} label={nav.switchLang} variante="campana" />
          {/* En móvil el idioma vive en el menú; desde lg va en la cabecera (arriba). */}
          <SedeSelector
            lang={lang}
            sedes={sedesDisponibles}
            sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
            placeholder={variante === 'hub' ? nav.eligeSede : undefined}
            label={nav.sedeLabel}
            className="hidden sm:inline-block"
          />
          <div className="hidden xl:block"><WhatsappContact nav={nav} tone="plain" /></div>

          <Button
            variante="libre"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className="flex size-11 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors hover:bg-borde xl:hidden"
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
              className="absolute inset-x-0 top-full flex flex-col bg-superficie px-4 py-2 shadow-n2 sm:px-6 lg:mt-2 xl:hidden"
            >
              {/* El mapa solo existe desde 1024 px: el menú móvil no lo ofrece. */}
              {links.filter((link) => !link.href.endsWith(`#${ANCLA_HUB.mapa}`)).map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="flex min-h-11 items-center py-3 texto-cuerpo font-semibold"
                >
                  {link.label}
                </Link>
              ))}
              <div className="flex items-center justify-between py-3.5">
                <span className="texto-cuerpo">{nav.sedeLabel}</span>
                <SedeSelector
                  lang={lang}
                  sedes={sedesDisponibles}
                  sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
                  placeholder={variante === 'hub' ? nav.eligeSede : undefined}
                  label={nav.sedeLabel}
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
