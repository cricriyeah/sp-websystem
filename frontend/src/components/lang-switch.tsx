'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { CaretDown, Check } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';

type LangSwitchProps = {
  lang: Locale;
  label: string;
  placement?: 'bottom' | 'top';
  align?: 'left' | 'right';
  className?: string;
};

function MexicoFlag({ className = 'h-3.5 w-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 480" className={`shrink-0 overflow-hidden border border-border/40 ${className}`} aria-hidden="true">
      <g fillRule="evenodd">
        <path fill="#fff" d="M0 0h640v480H0z"/>
        <path fill="#006847" d="M0 0h213.3v480H0z"/>
        <path fill="#ce1126" d="M426.7 0H640v480H426.7z"/>
        <circle cx="320" cy="240" r="32" fill="#b08b59" />
        <circle cx="320" cy="240" r="18" fill="#5d4037" />
        <path d="M308 248c6 10 18 10 24 0" stroke="#006847" strokeWidth="4" fill="none"/>
      </g>
    </svg>
  );
}

function USFlag({ className = 'h-3.5 w-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 480" className={`shrink-0 overflow-hidden border border-border/40 ${className}`} aria-hidden="true">
      <g fillRule="evenodd">
        <path fill="#bd3d44" d="M0 0h640v480H0z"/>
        <path stroke="#fff" strokeWidth="37" d="M0 55.5h640M0 129.5h640M0 203.5h640M0 277.5h640M0 351.5h640M0 425.5h640"/>
        <path fill="#192f5d" d="M0 0h280v259H0z"/>
        <g fill="#fff">
          <circle cx="45" cy="40" r="10" />
          <circle cx="95" cy="40" r="10" />
          <circle cx="145" cy="40" r="10" />
          <circle cx="195" cy="40" r="10" />
          <circle cx="245" cy="40" r="10" />
          <circle cx="70" cy="85" r="10" />
          <circle cx="120" cy="85" r="10" />
          <circle cx="170" cy="85" r="10" />
          <circle cx="220" cy="85" r="10" />
          <circle cx="45" cy="130" r="10" />
          <circle cx="95" cy="130" r="10" />
          <circle cx="145" cy="130" r="10" />
          <circle cx="195" cy="130" r="10" />
          <circle cx="245" cy="130" r="10" />
          <circle cx="70" cy="175" r="10" />
          <circle cx="120" cy="175" r="10" />
          <circle cx="170" cy="175" r="10" />
          <circle cx="220" cy="175" r="10" />
          <circle cx="45" cy="220" r="10" />
          <circle cx="95" cy="220" r="10" />
          <circle cx="145" cy="220" r="10" />
          <circle cx="195" cy="220" r="10" />
          <circle cx="245" cy="220" r="10" />
        </g>
      </g>
    </svg>
  );
}

const LOCALES: { value: Locale; Flag: typeof MexicoFlag; label: string }[] = [
  { value: 'es', Flag: MexicoFlag, label: 'Español' },
  { value: 'en', Flag: USFlag, label: 'English' },
];

/**
 * Selector de idioma personalizado con animación.
 * Esquinas rectas sin bordes redondeados.
 * Click fuera o Escape cierra el panel.
 */
export function LangSwitch({
  lang,
  label,
  placement = 'bottom',
  align = 'right',
  className = '',
}: LangSwitchProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  const sinMovimiento = useReducedMotion();

  const current = LOCALES.find((l) => l.value === lang)!;

  /* Cierre al hacer click fuera */
  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onOutside);
    return () => document.removeEventListener('mousedown', onOutside);
  }, []);

  /* Cierre con Escape */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  function select(locale: Locale) {
    setOpen(false);
    if (locale === lang) return;
    const next = pathname.replace(/^\/(es|en)/, `/${locale}`);
    router.push(next);
  }

  const isTop = placement === 'top';

  return (
    <div ref={ref} className={`relative ${className}`} aria-label={label}>
      {/* ── Trigger ─────────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        className="flex h-9 items-center gap-2 border border-border bg-background px-3 text-xs font-semibold text-foreground shadow-sm transition-colors hover:border-border-strong hover:bg-surface"
      >
        <current.Flag className="h-3.5 w-5" />
        <span className="uppercase tracking-wider">{current.value}</span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center text-muted"
          aria-hidden="true"
        >
          <CaretDown size={11} weight="bold" />
        </motion.span>
      </button>

      {/* ── Panel desplegable ────────────────────────────────────────────── */}
      <AnimatePresence>
        {open && (
          <motion.ul
            role="listbox"
            aria-label={label}
            initial={
              sinMovimiento
                ? { opacity: 0 }
                : { opacity: 0, y: isTop ? 6 : -6, scale: 0.98 }
            }
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={
              sinMovimiento
                ? { opacity: 0 }
                : { opacity: 0, y: isTop ? 4 : -4, scale: 0.98 }
            }
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className={`absolute z-50 min-w-[140px] border border-border bg-background shadow-[0_12px_32px_rgba(0,0,0,0.14)] ${
              isTop ? 'bottom-full mb-2' : 'top-full mt-2'
            } ${align === 'left' ? 'left-0' : 'right-0'}`}
          >
            {LOCALES.map((locale) => {
              const active = locale.value === lang;
              return (
                <li key={locale.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => select(locale.value)}
                    className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm transition-colors
                      ${active
                        ? 'bg-surface font-semibold text-foreground'
                        : 'text-muted hover:bg-surface hover:text-foreground'
                      }`}
                  >
                    <locale.Flag className="h-3.5 w-5" />
                    <span className="flex-1">{locale.label}</span>
                    {active && (
                      <Check
                        size={13}
                        weight="bold"
                        className="text-accent"
                        aria-hidden="true"
                      />
                    )}
                  </button>
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
