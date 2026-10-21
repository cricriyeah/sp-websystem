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
import { cn } from '@/components/ui/cn';

// La lista se abre como un círculo que crece desde el botón (arriba a la derecha de su caja).
const ABRE_CERRADO = 'circle(0% at calc(100% - 1.5rem) 0%)';
const ABRE_ABIERTO = 'circle(150% at calc(100% - 1.5rem) 0%)';

export type SedeOpcion = Pick<SedeIndiceEntry, 'slug' | 'nombre'>;

type SedeSelectorProps = {
  lang: Locale;
  sedes?: SedeOpcion[];
  sedeSeleccionadaSlug?: string;
  label?: string;
  placeholder?: string;
  onSelectSede?: (sede: SedeOpcion) => void;
  /** Un círculo negro con el icono; al tocarlo, la lista se abre desde él. Sin él, la píldora con el nombre. */
  compacto?: boolean;
  className?: string;
};

export function SedeSelector({
  lang,
  sedes: sedesProp,
  sedeSeleccionadaSlug,
  label = 'Destino',
  placeholder,
  onSelectSede,
  compacto = false,
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

  const puedeAbrir = sedes.length > 0;
  const nombreMostrado = sedeActiva?.nombre ?? placeholder ?? label;

  return (
    // `cn` y no plantilla: con `hidden sm:inline-block` desde la cabecera, el `inline-block` propio
    // ganaba y el selector se veía en móvil, empujando el botón de menú fuera de la pantalla.
    <div ref={ref} className={cn('relative inline-block text-left', className)}>
      {compacto ? (
        <Button
          variante="libre"
          disabled={!puedeAbrir}
          onClick={() => puedeAbrir && setOpen((v) => !v)}
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-label={`${label}: ${nombreMostrado}`}
          className="flex size-12 items-center justify-center rounded-full bg-tinta text-white transition-[background-color,transform] duration-150 hover:bg-cafe active:scale-[0.96] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-cafe-bruma disabled:text-apagado"
        >
          <MapPin size={22} weight="fill" aria-hidden="true" />
        </Button>
      ) : (
        <Button
          variante="libre"
          disabled={!puedeAbrir}
          onClick={() => puedeAbrir && setOpen((v) => !v)}
          aria-expanded={open}
          aria-haspopup="listbox"
          className="flex min-h-12 items-center gap-2 rounded-full bg-cafe-bruma px-5 texto-cuerpo font-semibold text-foreground transition-[background-color,transform] duration-150 hover:bg-borde active:scale-[0.98] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-cafe-bruma disabled:text-apagado"
        >
          <MapPin size={18} className="shrink-0" weight="fill" aria-hidden="true" />
          <span className="hidden sm:inline">{label}:</span>
          <span>{nombreMostrado}</span>
          <CaretDown
            size={14}
            weight="bold"
            className={`shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </Button>
      )}

      <AnimatePresence>
        {open && puedeAbrir && (
          <m.div
            role="listbox"
            aria-label={label}
            initial={sinMovimiento ? { opacity: 0 } : compacto ? { opacity: 0, clipPath: ABRE_CERRADO } : { opacity: 0, y: -4, scale: 0.98 }}
            animate={compacto && !sinMovimiento ? { opacity: 1, clipPath: ABRE_ABIERTO } : { opacity: 1, y: 0, scale: 1 }}
            exit={sinMovimiento ? { opacity: 0 } : compacto ? { opacity: 0, clipPath: ABRE_CERRADO } : { opacity: 0, y: -4, scale: 0.98 }}
            transition={compacto && !sinMovimiento ? { duration: 0.45, ease: [0.16, 1, 0.3, 1] } : { duration: 0.15, ease: 'easeOut' }}
            className={cn(
              'absolute top-full z-50 mt-3 min-w-[15rem] rounded-sheet bg-superficie p-2 shadow-n2',
              compacto ? 'right-0' : 'left-0',
            )}
          >
            {sedes.map((s) => {
              const selected = sedeActiva?.slug === s.slug;
              return (
                <Button
                  key={s.slug}
                  variante="libre"
                  role="option"
                  aria-selected={selected}
                  onClick={() => handleSelect(s)}
                  className={`flex min-h-12 w-full items-center justify-between gap-3 rounded-full px-4 py-2 text-left texto-cuerpo transition-colors ${
                    selected
                      ? 'bg-tinta font-semibold text-white'
                      : 'text-foreground hover:bg-cafe-bruma'
                  }`}
                >
                  <span>{s.nombre}</span>
                  {selected && <Check size={16} weight="bold" aria-hidden="true" />}
                </Button>
              );
            })}
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
