'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Fish, List, X } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
};

export function SiteHeader({ lang, nav }: SiteHeaderProps) {
  const [open, setOpen] = useState(false);

  const links = [
    { href: '#inicio', label: nav.inicio },
    { href: '#nosotros', label: nav.nosotros },
    { href: '#preguntas', label: nav.preguntas },
  ];

  return (
    <header className="relative z-20 shrink-0">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6 sm:px-8 lg:h-20 lg:px-12">
        <Link
          href={`/${lang}`}
          className="flex items-center gap-2.5 text-hero-ink"
          onClick={() => setOpen(false)}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-hero-ink text-surface">
            <Fish size={18} weight="fill" />
          </span>
          <span className="hidden flex-col sm:flex">
            <span className="pb-0.5 text-sm leading-[1.2] font-medium tracking-tight">
              {nav.brandMain} <span className="italic font-light">{nav.brandAccent}</span>
            </span>
            <span className="text-xs text-hero-ink-soft">{nav.location}</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-8 lg:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-hero-ink-soft transition-colors hover:text-hero-ink"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="#contacto"
            className="hidden rounded-full border border-hero-ink/25 px-5 py-2.5 text-sm text-hero-ink transition-colors hover:bg-hero-ink hover:text-surface lg:inline-block"
          >
            {nav.contacto}
          </Link>

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-hero-ink/25 text-hero-ink lg:hidden"
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
          <Link
            href="#contacto"
            onClick={() => setOpen(false)}
            className="mt-1 rounded-xl border border-border px-4 py-2.5 text-center text-sm text-foreground"
          >
            {nav.contacto}
          </Link>
        </div>
      ) : null}
    </header>
  );
}
