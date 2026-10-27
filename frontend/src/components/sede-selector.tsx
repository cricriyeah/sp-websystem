'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { CaretDown, Check, House, MapPin } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE, getSedeIndice } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { guardarSedePreferida, leerSedePreferidaCliente } from '@/lib/sede';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';
import { Despliegue } from '@/components/ui/despliegue';
import { DURACION } from '@/lib/movimiento';

// Compacto: el círculo se estira a píldora hacia la izquierda y, ya abierta, la lista cae desde ella.
// Al cerrar, el orden se invierte: primero se recoge la lista y después la píldora vuelve a círculo.
const LISTA_CERRADA = 'inset(0 -20px 100% -20px)';
const LISTA_ABIERTA = 'inset(-20px -20px -40px -20px)';
const CURVA = [0.16, 1, 0.3, 1] as const;

export type SedeOpcion = Pick<SedeIndiceEntry, 'slug' | 'nombre'>;

// Lo que crece el círculo (48 px) al estirarse a píldora (240 px), más un respiro con lo que queda a su izquierda.
const CRECE_AL_ESTIRAR = 192;
const RESPIRO = 12;

/**
 * La píldora compacta crece dentro de la barra y empuja a sus vecinos hacia la izquierda, así que solo se
 * estira si entre el grupo de controles y lo que tiene antes hay sitio de sobra. Si no, se queda círculo y
 * la lista cae debajo: nunca se sale de la barra ni tapa nada.
 */
function hayEspacioParaEstirar(caja: HTMLElement | null): boolean {
  const grupo = caja?.parentElement;
  if (!grupo) return false;
  let previo = grupo.previousElementSibling as HTMLElement | null;
  while (previo && previo.offsetWidth === 0) previo = previo.previousElementSibling as HTMLElement | null;
  if (!previo) return false;
  return grupo.getBoundingClientRect().left - previo.getBoundingClientRect().right >= CRECE_AL_ESTIRAR + RESPIRO;
}

type SedeSelectorProps = {
  lang: Locale;
  sedes?: SedeOpcion[];
  sedeSeleccionadaSlug?: string;
  label?: string;
  placeholder?: string;
  onSelectSede?: (sede: SedeOpcion) => void;
  /** Un círculo negro con el icono; al tocarlo, la lista se abre desde él. Sin él, la píldora con el nombre. */
  compacto?: boolean;
  /** Si llega, la lista cierra con una opción que vuelve a la portada con todos los destinos. */
  inicioLabel?: string;
  /** Ocupa todo el ancho de su contenedor (menú móvil): la píldora y la lista. */
  anchoCompleto?: boolean;
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
  anchoCompleto = false,
  inicioLabel,
  className = '',
}: SedeSelectorProps) {
  const [open, setOpen] = useState(false);
  // Compacto: si al abrir hay sitio, la píldora se estira; si no, queda círculo (ver `hayEspacioParaEstirar`).
  const [estira, setEstira] = useState(true);
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

  // Ya desplegada la lista del menú móvil, la lleva a la vista dentro del panel que se desplaza: si
  // cabe entera, lo justo para verla; si no, con el disparador arriba y las opciones debajo.
  useEffect(() => {
    if (!open || !anchoCompleto) return;
    const espera = window.setTimeout(() => {
      const caja = ref.current;
      const panel = caja?.closest<HTMLElement>('[data-panel-desplazable]');
      if (!caja || !panel) return;
      caja.scrollIntoView({
        block: caja.offsetHeight <= panel.clientHeight ? 'nearest' : 'start',
        behavior: sinMovimiento ? 'auto' : 'smooth',
      });
    }, DURACION.media * 1000);
    return () => window.clearTimeout(espera);
  }, [open, anchoCompleto, sinMovimiento]);

  const puedeAbrir = sedes.length > 0;
  const nombreMostrado = sedeActiva?.nombre ?? placeholder ?? label;

  const opciones = (
    <>
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
      {inicioLabel && <div aria-hidden="true" className="mx-4 my-1 h-px bg-borde" />}
      {inicioLabel && (
        <Button
          variante="libre"
          role="option"
          aria-selected={false}
          onClick={() => { setOpen(false); router.push(hrefInicio(lang)); }}
          className="flex min-h-12 w-full items-center gap-3 rounded-full px-4 py-2 text-left texto-cuerpo text-foreground transition-colors hover:bg-cafe-bruma"
        >
          <House size={16} weight="bold" aria-hidden="true" />
          <span>{inicioLabel}</span>
        </Button>
      )}
    </>
  );

  return (
    // `cn` y no plantilla: con `hidden sm:inline-block` desde la cabecera, el `inline-block` propio
    // ganaba y el selector se veía en móvil, empujando el botón de menú fuera de la pantalla.
    // `cn` y no plantilla: con `hidden sm:inline-block` desde la cabecera, el `inline-block` propio
    // ganaba y el selector se veía en móvil, empujando el botón de menú fuera de la pantalla.
    <div ref={ref} className={cn('relative inline-block text-left', anchoCompleto && 'block w-full', className)}>
      {compacto ? (
        <div
          className={cn(
            'relative h-12 max-w-[calc(100vw-2rem)] overflow-hidden rounded-full bg-tinta text-white transition-[width] duration-[420ms] ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none',
            open && estira ? 'w-60' : open ? 'w-12' : 'w-12 delay-[160ms]',
          )}
        >
            <Button
              variante="libre"
              disabled={!puedeAbrir}
              onClick={() => {
                if (!puedeAbrir) return;
                if (!open) setEstira(hayEspacioParaEstirar(ref.current));
                setOpen((v) => !v);
              }}
              aria-expanded={open}
              aria-haspopup="listbox"
              aria-label={`${label}: ${nombreMostrado}`}
              className="flex h-full w-full items-center justify-end transition-colors duration-150 hover:bg-cafe active:scale-[0.98] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-cafe-bruma disabled:text-apagado"
            >
              <span
                aria-hidden="true"
                className={cn('min-w-0 flex-1 truncate pl-5 text-left texto-cuerpo font-semibold transition-opacity duration-200', open && estira ? 'opacity-100 delay-150' : 'opacity-0')}
              >
                {nombreMostrado}
              </span>
              <span className="flex size-12 shrink-0 items-center justify-center">
                <MapPin size={22} weight="fill" aria-hidden="true" />
              </span>
            </Button>
        </div>
      ) : (
        <Button
          variante="libre"
          disabled={!puedeAbrir}
          onClick={() => puedeAbrir && setOpen((v) => !v)}
          aria-expanded={open}
          aria-haspopup="listbox"
          className={cn('flex min-h-12 items-center gap-2 rounded-full bg-cafe-bruma px-5 texto-cuerpo font-semibold text-foreground transition-[background-color,transform] duration-150 hover:bg-borde active:scale-[0.98] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-cafe-bruma disabled:text-apagado', anchoCompleto && 'w-full')}
        >
          <MapPin size={18} className="shrink-0" weight="fill" aria-hidden="true" />
          <span className="hidden sm:inline">{label}:</span>
          <span>{nombreMostrado}</span>
          <CaretDown
            size={14}
            weight="bold"
            className={cn('shrink-0 transition-transform duration-200', open && 'rotate-180', anchoCompleto && 'ml-auto')}
          />
        </Button>
      )}

      {anchoCompleto ? (
        // En el menú móvil la lista no flota: se despliega dentro del panel, empujando lo de abajo.
        // Una hoja flotante colgaba del borde del panel y la pantalla la recortaba.
        <Despliegue abierto={open && puedeAbrir}>
          <div role="listbox" aria-label={label} className="pt-2">
            {opciones}
          </div>
        </Despliegue>
      ) : (
        <AnimatePresence>
          {open && puedeAbrir && (
            <m.div
              role="listbox"
              aria-label={label}
              initial={sinMovimiento ? { opacity: 0 } : compacto ? { opacity: 0, clipPath: LISTA_CERRADA } : { opacity: 0, y: -4, scale: 0.98 }}
              animate={sinMovimiento ? { opacity: 1 } : compacto ? { opacity: 1, clipPath: LISTA_ABIERTA } : { opacity: 1, y: 0, scale: 1 }}
              exit={sinMovimiento ? { opacity: 0 } : compacto ? { opacity: 0, clipPath: LISTA_CERRADA } : { opacity: 0, y: -4, scale: 0.98 }}
              transition={compacto && !sinMovimiento ? { duration: 0.34, ease: CURVA, delay: estira ? 0.3 : 0 } : { duration: 0.15, ease: 'easeOut' }}
              className={cn(
                'absolute right-0 top-full z-50 mt-3 rounded-sheet bg-superficie p-2 shadow-n2',
                compacto ? 'w-60 max-w-[calc(100vw-2rem)]' : 'w-max min-w-[15rem] max-w-[calc(100vw-2rem)]',
              )}
            >
              {opciones}
            </m.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
