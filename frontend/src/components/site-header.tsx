'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Fish, List, X } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { WhatsappContact } from '@/components/whatsapp-contact';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
  /**
   * `hero` va encima del degradado turquesa de la portada; `plain` sobre el
   * fondo normal de las demas paginas (checkout, deslinde, confirmacion).
   */
  tone?: 'hero' | 'plain';
};

const ESTILOS = {
  hero: {
    contenedor: 'relative z-20 shrink-0',
    marca: 'text-hero-ink',
    circulo: 'bg-hero-ink text-surface',
    sublinea: 'text-hero-ink-soft',
    enlace: 'text-hero-ink-soft hover:text-hero-ink',
    boton: 'border-hero-ink/25 text-hero-ink',
  },
  plain: {
    contenedor: 'relative z-20 shrink-0 border-b border-border bg-background',
    marca: 'text-foreground',
    circulo: 'bg-foreground text-surface',
    sublinea: 'text-muted',
    enlace: 'text-muted hover:text-foreground',
    boton: 'border-border text-foreground',
  },
};

export function SiteHeader({ lang, nav, tone = 'hero' }: SiteHeaderProps) {
  const [open, setOpen] = useState(false);
  const estilo = ESTILOS[tone];

  // Absolutos y no anclas sueltas: desde el checkout o el deslinde, un `#nosotros`
  // no llevaria a ningun lado porque esas secciones viven en la portada.
  const links = [
    { href: `/${lang}#nosotros`, label: nav.nosotros },
    { href: `/${lang}#flota`, label: nav.flota },
    { href: `/${lang}#temporadas`, label: nav.temporadas },
    { href: `/${lang}#preguntas`, label: nav.preguntas },
  ];

  return (
    <header className={estilo.contenedor}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6 sm:px-8 lg:h-20 lg:px-12">
        <Link
          href={`/${lang}`}
          className={`flex items-center gap-2.5 ${estilo.marca}`}
          onClick={() => setOpen(false)}
        >
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${estilo.circulo}`}
          >
            <Fish size={18} weight="fill" />
          </span>
          <span className="hidden flex-col sm:flex">
            <span className="pb-0.5 text-sm leading-[1.2] font-medium tracking-tight">
              {nav.brandMain} <span className="italic font-light">{nav.brandAccent}</span>
            </span>
            <span className={`text-xs ${estilo.sublinea}`}>{nav.location}</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-8 lg:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm transition-colors ${estilo.enlace}`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <WhatsappContact nav={nav} tone={tone} />

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className={`flex h-10 w-10 items-center justify-center rounded-full border lg:hidden ${estilo.boton}`}
          >
            {open ? <X size={18} /> : <List size={18} />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="mx-6 mt-2 flex flex-col gap-1 rounded-2xl border border-border bg-surface p-3 shadow-[0_16px_40px_rgba(11,36,32,0.14)] sm:mx-8 lg:hidden">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="rounded-xl px-4 py-2.5 text-sm text-muted transition-colors hover:bg-background hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
          <WhatsappContact nav={nav} variant="menu" />
        </div>
      ) : null}
    </header>
  );
}
