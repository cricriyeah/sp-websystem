'use client';

import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { cn } from '@/components/ui/cn';

/**
 * Lo que cambió el último toque, junto al control que lo provocó (PFD, 2026-10-22): «+$1,350», «−$1,350» o «Sin
 * costo». Cada control que puede mover el precio (contador de personas, extras, tipo de traslado) llama a
 * `marcar()` al tocarse; el proveedor compara el total de la ruta antes y después del toque y deja la píldora en
 * ese control unos instantes. Un toque que no cambia el total también responde («Sin costo»): saber que algo no
 * cuesta es parte de la respuesta. Para el lector de pantalla, el nuevo total en una región `polite`.
 */

const DURACION_MS = 1600;

type Pildora = { id: string; delta: number; clave: number };
type Contexto = {
  marcar: (id: string) => void;
  pildora: Pildora | null;
  formatear: (monto: number) => string;
  sinCosto: string;
};

const ContextoCambio = createContext<Contexto | null>(null);

type Props = {
  /** El total del pedido en la moneda de la página; `null` mientras no se puede calcular. */
  total: number | null;
  formatear: (monto: number) => string;
  textos: { sinCosto: string; anuncio: string };
  children: ReactNode;
};

export function ProveedorCambioPrecio({ total, formatear, textos, children }: Props) {
  const origen = useRef<string | null>(null);
  const anterior = useRef(total);
  // Un toque que no mueve el total no cambia `total`: el contador de toques hace que el efecto corra igual.
  const [toques, setToques] = useState(0);
  const [pildora, setPildora] = useState<Pildora | null>(null);
  const [anuncio, setAnuncio] = useState('');
  // El reloj vive fuera del efecto: si `formatear` cambia de identidad el efecto vuelve a correr, y su limpieza
  // no debe borrar el reloj de una píldora que ya se está mostrando.
  const reloj = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(reloj.current), []);

  const marcar = useCallback((id: string) => {
    origen.current = id;
    setToques((n) => n + 1);
  }, []);

  useEffect(() => {
    const antes = anterior.current;
    anterior.current = total;
    const id = origen.current;
    origen.current = null;
    if (!id || antes === null || total === null) return;
    const delta = Math.round((total - antes) * 100) / 100;
    setPildora({ id, delta, clave: Date.now() });
    setAnuncio(textos.anuncio.replace('{total}', formatear(total)));
    clearTimeout(reloj.current);
    reloj.current = setTimeout(() => setPildora(null), DURACION_MS);
  }, [total, toques, formatear, textos.anuncio]);

  const valor = useMemo(() => ({ marcar, pildora, formatear, sinCosto: textos.sinCosto }), [marcar, pildora, formatear, textos.sinCosto]);
  return (
    <ContextoCambio.Provider value={valor}>
      {children}
      <p className="sr-only" aria-live="polite">{anuncio}</p>
    </ContextoCambio.Provider>
  );
}

/** Para un control que puede mover el precio: `marcar` al tocarlo y `pildora` para pintar junto a él. */
export function useCambioPrecio(className?: string) {
  const contexto = useContext(ContextoCambio);
  const id = useId();
  const marcar = useCallback(() => contexto?.marcar(id), [contexto, id]);
  const pildora = contexto ? <PildoraCambio id={id} contexto={contexto} className={className} /> : null;
  return { marcar, pildora };
}

/** `useCambioPrecio` para lo que se pinta dentro de un `map` (cada extra), donde no se puede llamar un hook. */
export function ConCambioPrecio({ className, children }: {
  className?: string;
  children: (cambio: ReturnType<typeof useCambioPrecio>) => ReactNode;
}) {
  return <>{children(useCambioPrecio(className))}</>;
}

function PildoraCambio({ id, contexto, className }: { id: string; contexto: Contexto; className?: string }) {
  const sinMovimiento = useReducedMotion();
  const { pildora, formatear, sinCosto } = contexto;
  const visible = pildora?.id === id ? pildora : null;
  const texto = visible
    ? visible.delta > 0 ? `+${formatear(visible.delta)}` : visible.delta < 0 ? `−${formatear(-visible.delta)}` : sinCosto
    : '';
  return (
    <AnimatePresence>
      {visible && (
        <m.span
          key={visible.clave}
          aria-hidden="true"
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -4 }}
          transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
          className={cn(
            'pointer-events-none absolute z-10 whitespace-nowrap rounded-full px-3 py-1 texto-pequeno font-semibold tabular-nums shadow-n2',
            visible.delta === 0 ? 'bg-cafe-bruma text-foreground' : 'bg-tinta text-white',
            className ?? '-top-3 right-3',
          )}
        >
          {texto}
        </m.span>
      )}
    </AnimatePresence>
  );
}
