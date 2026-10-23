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
import { BarraFlotante, LogoEmpresaAlLado, LogoMarca } from '@/components/barra-flotante';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { SelectorIdioma } from '@/components/selector-idioma';
import { SedeSelector } from '@/components/sede-selector';
import { ContinuarReservacion } from '@/components/continuar-reservacion';
import { Button } from '@/components/ui/button';

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
   * las secciones que de verdad se pintan. «Reserva ahora» va primero y baja a la sección de reservar.
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

  // Con el menú abierto, bajar por la página lo cierra (con su animación de salida).
  useEffect(() => {
    if (!open) return;
    const inicio = window.scrollY;
    const alDesplazar = () => { if (window.scrollY - inicio > 24) setOpen(false); };
    window.addEventListener('scroll', alDesplazar, { passive: true });
    return () => window.removeEventListener('scroll', alDesplazar);
  }, [open]);

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

  const idioma = <SelectorIdioma lang={lang} label={nav.switchLang} variante="campana" />;
  const alPulsarEnlace = () => setOpen(false);

  const menu = (
    <AnimatePresence>
      {open && (
        <m.div
          key="menu-movil"
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="absolute inset-x-0 top-[calc(var(--barra-h)+0.5rem)] z-10 flex flex-col rounded-sheet bg-superficie px-6 py-3 shadow-n2 xl:hidden"
        >
          {/* El mapa solo existe desde 1024 px: el menú móvil no lo ofrece. */}
          {links.filter((link) => !link.href.endsWith(`#${ANCLA_HUB.mapa}`)).map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={alPulsarEnlace}
              className="flex min-h-11 items-center py-3 texto-cuerpo font-semibold"
            >
              {link.label}
            </Link>
          ))}
          <div className="flex flex-col gap-2 py-3.5">
            <span className="texto-cuerpo">{nav.sedeLabel}</span>
            <SedeSelector
              lang={lang}
              sedes={sedesDisponibles}
              sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
              placeholder={variante === 'hub' ? nav.eligeSede : undefined}
              label={nav.sedeLabel}
              inicioLabel={variante === 'hub' ? undefined : nav.todosLosDestinos}
              anchoCompleto
            />
          </div>
          <div className="py-3">
            <WhatsappContact nav={nav} variant="menu" />
          </div>
        </m.div>
      )}
    </AnimatePresence>
  );

  return (
    <BarraFlotante
      className={className}
      inicio={
        <Link href={hrefInicio(lang)} className="inline-flex" onClick={alPulsarEnlace} aria-label={MARCA}>
          <LogoMarca girado={open} />
        </Link>
      }
      resto={
        <>
          <div className="flex min-w-0 shrink-0 items-center gap-3">
            <LogoEmpresaAlLado empresa={marcaSede} ocultoEnMovil />
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

          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            {links.length === 1 && (
              <Link
                href={links[0].href}
                className="hidden min-h-11 items-center texto-cuerpo transition-colors hover:text-cafe lg:inline-flex"
              >
                {links[0].label}
              </Link>
            )}
            {idioma}
            {variante !== 'hub' && <WhatsappContact nav={nav} tone="plain" />}
            <SedeSelector
              lang={lang}
              sedes={sedesDisponibles}
              sedeSeleccionadaSlug={variante === 'hub' ? undefined : slugActual}
              placeholder={variante === 'hub' ? nav.eligeSede : undefined}
              label={nav.sedeLabel}
              inicioLabel={variante === 'hub' ? undefined : nav.todosLosDestinos}
              compacto={variante !== 'hub'}
              className="hidden sm:inline-block"
            />

            <Button
              variante="libre"
              onClick={() => setOpen((v) => !v)}
              aria-label={open ? nav.closeMenu : nav.openMenu}
              aria-expanded={open}
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors hover:bg-borde xl:hidden"
            >
              {open ? <X size={18} /> : <List size={18} />}
            </Button>
          </div>
        </>
      }
      menu={menu}
      debajo={
        mostrarContinuar && continuar ? (
          <div ref={bandaRef} className="mt-2 w-full">
            <ContinuarReservacion lang={lang} dict={{ continuar }} />
          </div>
        ) : undefined
      }
    />
  );
}
