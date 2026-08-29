'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { CaretDown, Check } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';

type LangSwitchProps = {
  lang: Locale;
  label: string;
};

const LOCALES: { value: Locale; flag: string; label: string }[] = [
  { value: 'es', flag: '🇲🇽', label: 'Español' },
  { value: 'en', flag: '🇺🇸', label: 'English' },
];

/**
 * Selector de idioma personalizado con animación.
 * Usa motion/react (ya en el proyecto) para el panel desplegable.
 * Click fuera o Escape cierra el panel.
 */
export function LangSwitch({ lang, label }: LangSwitchProps) {
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

  return (
    <div ref={ref} className="relative" aria-label={label}>
      {/* ── Trigger ─────────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        className="flex h-8 items-center gap-1.5 rounded-full border border-border bg-background px-3 text-xs font-semibold text-foreground transition-colors hover:border-border-strong hover:bg-surface"
      >
        <span aria-hidden="true">{current.flag}</span>
        <span className="uppercase tracking-wide">{current.value}</span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center"
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
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            /* `right-0` para que no se salga por la derecha en el header */
            className="absolute right-0 top-full z-50 mt-2 min-w-[140px] overflow-hidden rounded-xl border border-border bg-background shadow-[0_8px_24px_rgba(0,0,0,0.1)]"
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
                    <span aria-hidden="true" className="text-base">{locale.flag}</span>
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
