'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { CaretDown, Check, MapPin } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE, getSedeIndice } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { guardarSedePreferida, leerSedePreferidaCliente } from '@/lib/sede';
import { hrefSede } from '@/lib/routes';
import { Button } from '@/components/ui/button';

export type SedeOpcion = Pick<SedeIndiceEntry, 'slug' | 'nombre'>;

type SedeSelectorProps = {
  lang: Locale;
  sedes?: SedeOpcion[];
  sedeSeleccionadaSlug?: string;
  label?: string;
  placeholder?: string;
  onSelectSede?: (sede: SedeOpcion) => void;
  variant?: 'header' | 'catalog';
  className?: string;
};

export function SedeSelector({
  lang,
  sedes: sedesProp,
  sedeSeleccionadaSlug,
  label = 'Destino',
  placeholder,
  onSelectSede,
  variant = 'catalog',
  className = '',
}: SedeSelectorProps) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);
  const sinMovimiento = useReducedMotion();

  // Slug de la sede activa. El catálogo lo pasa por prop; en el resto de páginas
  // (portada, checkout) no hay `?sede=` en la URL, así que se resuelve en el
  // cliente desde la query o desde la preferencia guardada. `usePathname()` en
  // las dependencias hace que se recalcule tras cada navegación SPA. Se lee
  // `window.location.search` y no `useSearchParams()` a propósito: ese hook
  // saca de la pre-renderización estática a toda página que lo monte (mismo
  // criterio que `ref-capture.tsx`).
  const [sedeSlugActiva, setSedeSlugActiva] = useState<string | undefined>(
    sedeSeleccionadaSlug,
  );

  /* eslint-disable react-hooks/set-state-in-effect -- sincroniza el estado con
     dos sistemas externos (la query de la URL y la preferencia guardada) tras
     cada navegación SPA; no se puede leer `window` en el render sin romper el
     SSR. Mismo criterio que booking-state.tsx / checkout-view.tsx. */
  useEffect(() => {
    if (placeholder) {
      setSedeSlugActiva(undefined);
      return;
    }
    if (sedeSeleccionadaSlug) {
      setSedeSlugActiva(sedeSeleccionadaSlug);
      return;
    }
    const enUrl = new URLSearchParams(window.location.search).get('sede') ?? undefined;
    setSedeSlugActiva(enUrl ?? leerSedePreferidaCliente());
  }, [pathname, sedeSeleccionadaSlug, placeholder]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // const sedes = sedesProp ?? Object.values(SEDES_INDICE): un [] explícito
  // significa que no hay sedes activas y nunca dispara fallback. El fallback al
  // índice es solo compatibilidad para callers que todavía omiten la prop.
  const sedes = sedesProp ?? Object.values(SEDES_INDICE);

  const slugActivo = placeholder ? undefined : sedeSeleccionadaSlug ?? sedeSlugActiva;
  const sedeActiva =
    sedes.find((sede) => sede.slug === slugActivo) ??
    (!placeholder && sedeSeleccionadaSlug ? getSedeIndice(sedeSeleccionadaSlug) : undefined);

  // Cierre al hacer click fuera
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open]);

  // Cierre con Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [open]);

  function handleSelect(sede: SedeOpcion) {
    setOpen(false);
    // Optimista: el selector refleja la nueva sede sin esperar a la navegación.
    setSedeSlugActiva(sede.slug);
    guardarSedePreferida(sede.slug);
    if (onSelectSede) {
      onSelectSede(sede);
    } else {
      router.push(hrefSede(lang, sede.slug));
    }
  }

  const isHeader = variant === 'header';
  const puedeAbrir = sedes.length > 0;
  const nombreMostrado = sedeActiva?.nombre ?? placeholder ?? label;

  return (
    <div ref={ref} className={`relative inline-block text-left ${className}`}>
      <Button
        variante="libre"
        disabled={!puedeAbrir}
        onClick={() => puedeAbrir && setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={
          isHeader
            ? 'flex items-center gap-1.5 rounded-full border border-border bg-superficie px-3 py-1.5 text-[13px] font-medium text-foreground transition-colors hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:cursor-not-allowed'
            : 'flex items-center gap-2.5 rounded-control border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground transition-all hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:cursor-not-allowed'
        }
      >
        <MapPin size={isHeader ? 14 : 18} className="shrink-0 text-accent" weight="fill" />
        <span className="text-muted text-xs hidden sm:inline">{label}:</span>
        <span className="font-semibold text-foreground">{nombreMostrado}</span>
        <CaretDown
          size={isHeader ? 12 : 14}
          className={`shrink-0 text-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </Button>

      <AnimatePresence>
        {open && puedeAbrir && (
          <m.div
            role="listbox"
            aria-label={label}
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className="absolute left-0 top-full z-50 mt-2 min-w-[200px] rounded-card border border-border bg-superficie p-1.5 shadow-n2"
          >
            <div className="px-3 py-1.5 texto-pie font-medium text-muted">
              {label}
            </div>
            {sedes.map((s) => {
              const selected = sedeActiva?.slug === s.slug;
              return (
                <Button
                  key={s.slug}
                  variante="libre"
                  role="option"
                  aria-selected={selected}
                  onClick={() => handleSelect(s)}
                  className={`flex w-full items-center justify-between gap-3 rounded-sm px-3 py-2 text-left text-sm transition-colors ${
                    selected
                      ? 'bg-accent/10 font-semibold text-accent'
                      : 'text-foreground hover:bg-muted/10'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <MapPin size={14} className={selected ? 'text-accent' : 'text-muted'} />
                    <span>{s.nombre}</span>
                  </div>
                  {selected && <Check size={14} weight="bold" className="text-accent" />}
                </Button>
              );
            })}
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
