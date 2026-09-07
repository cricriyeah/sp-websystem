'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { CaretDown, Check, MapPin } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { getSedes, type Sede } from '@/lib/api';
import { guardarSedePreferida, leerSedePreferidaCliente } from '@/lib/sede';

type SedeSelectorProps = {
  lang: Locale;
  sedes?: Sede[];
  sedeSeleccionadaSlug?: string;
  label?: string;
  onSelectSede?: (sede: Sede) => void;
  variant?: 'header' | 'catalog';
  className?: string;
};

export function SedeSelector({
  lang,
  sedes: sedesProp,
  sedeSeleccionadaSlug,
  label = 'Destino',
  onSelectSede,
  variant = 'catalog',
  className = '',
}: SedeSelectorProps) {
  const [open, setOpen] = useState(false);
  const [sedesFetched, setSedesFetched] = useState<Sede[]>([]);
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
    if (sedeSeleccionadaSlug) {
      setSedeSlugActiva(sedeSeleccionadaSlug);
      return;
    }
    const enUrl = new URLSearchParams(window.location.search).get('sede') ?? undefined;
    setSedeSlugActiva(enUrl ?? leerSedePreferidaCliente());
  }, [pathname, sedeSeleccionadaSlug]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Si no se proporcionaron sedes desde el servidor, se cargan en cliente
  useEffect(() => {
    if (sedesProp && sedesProp.length > 0) return;
    let montado = true;
    getSedes()
      .then((data) => {
        if (montado && data) setSedesFetched(data);
      })
      .catch(() => {
        // Fallback defensivo a La Paz si la red falla
        if (montado) {
          setSedesFetched([{ id: 1, nombre: 'La Paz', slug: 'la-paz', zona_horaria: 'America/Mazatlan' }]);
        }
      });
    return () => {
      montado = false;
    };
  }, [sedesProp]);

  const sedes = sedesProp && sedesProp.length > 0 ? sedesProp : sedesFetched;

  // Sede actualmente activa
  const sedeActiva =
    sedes.find((s) => s.slug === sedeSlugActiva) ??
    sedes[0] ?? {
      id: 1,
      nombre: 'La Paz',
      slug: 'la-paz',
      zona_horaria: 'America/Mazatlan',
    };

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

  function handleSelect(sede: Sede) {
    setOpen(false);
    // Optimista: el selector refleja la nueva sede sin esperar a la navegación.
    setSedeSlugActiva(sede.slug);
    guardarSedePreferida(sede.slug);
    if (onSelectSede) {
      onSelectSede(sede);
    } else {
      router.push(`/${lang}/catalogo?sede=${sede.slug}`);
    }
  }

  const isHeader = variant === 'header';

  return (
    <div ref={ref} className={`relative inline-block text-left ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={
          isHeader
            ? 'flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-[13px] font-medium text-foreground transition-colors hover:border-accent hover:text-accent focus:outline-none focus:ring-1 focus:ring-accent'
            : 'flex items-center gap-2.5 rounded-xl border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground shadow-sm transition-all hover:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20'
        }
      >
        <MapPin size={isHeader ? 14 : 18} className="shrink-0 text-accent" weight="fill" />
        <span className="text-muted text-xs hidden sm:inline">{label}:</span>
        <span className="font-semibold text-foreground">{sedeActiva.nombre}</span>
        <CaretDown
          size={isHeader ? 12 : 14}
          className={`shrink-0 text-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="listbox"
            aria-label={label}
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className="absolute left-0 top-full z-50 mt-2 min-w-[200px] rounded-xl border border-border bg-surface p-1.5 shadow-[0_12px_32px_rgba(11,36,32,0.14)]"
          >
            <div className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-muted">
              {label}
            </div>
            {sedes.map((s) => {
              const selected = s.slug === sedeActiva.slug;
              return (
                <button
                  key={s.slug}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => handleSelect(s)}
                  className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
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
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
