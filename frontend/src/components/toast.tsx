'use client';

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { CheckCircle, Info, Warning, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

/**
 * Avisos del sistema. Un solo lenguaje visual para todo lo que la pagina le dice
 * al cliente.
 *
 * Antes habia tres dialectos distintos —una frase roja al pie del panel de pago,
 * un cambio de texto en el boton, una barra ambar arriba del checkout— y cada
 * dialecto extra cuesta esfuerzo de decodificacion. El esfuerzo se siente como
 * poca confiabilidad, justo en la pantalla donde el cliente esta decidiendo si
 * te da 4,500 pesos.
 *
 * Dos reglas que no son de estilo:
 *
 * - **Un error que exige accion NO va aqui.** Los toasts se auto-descartan; si
 *   el mensaje que explica un formulario roto desaparece solo, el cliente queda
 *   con el problema y sin la explicacion. Esto es para lo que informa. Lo que
 *   bloquea vive pegado a su campo o en un bloque que persiste.
 * - **Arriba-centro en movil, arriba-derecha en escritorio.** La esquina
 *   superior derecha es el punto mas lejano del pulgar y donde vive el notch, y
 *   los clientes de este sitio son turistas con el telefono en la mano.
 */

export type TipoToast = 'exito' | 'error' | 'info';

type Toast = {
  id: number;
  tipo: TipoToast;
  mensaje: string;
};

type ContextoToast = {
  mostrar: (tipo: TipoToast, mensaje: string) => void;
};

const Contexto = createContext<ContextoToast | null>(null);

/** Cuanto vive un aviso. Lo suficiente para leerlo en el idioma mas largo. */
const DURACION_MS = 6000;

const ICONOS = { exito: CheckCircle, error: Warning, info: Info } as const;

const COLORES = {
  exito: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  info: 'border-accent/40 bg-accent/10 text-foreground',
} as const;

const COLOR_ICONO = {
  exito: 'text-emerald-600',
  error: 'text-red-600',
  info: 'text-accent',
} as const;

export function ProveedorToast({
  children,
  cerrarLabel,
}: {
  children: ReactNode;
  cerrarLabel: string;
}) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const reduce = useReducedMotion();

  const descartar = useCallback((id: number) => {
    setToasts((actuales) => actuales.filter((t) => t.id !== id));
  }, []);

  const mostrar = useCallback(
    (tipo: TipoToast, mensaje: string) => {
      const id = Date.now() + Math.random();
      setToasts((actuales) => [...actuales, { id, tipo, mensaje }]);
      window.setTimeout(() => descartar(id), DURACION_MS);
    },
    [descartar],
  );

  const valor = useMemo(() => ({ mostrar }), [mostrar]);

  return (
    <Contexto.Provider value={valor}>
      {children}

      {/* aria-live para que un lector de pantalla anuncie el aviso sin sacar al
          cliente de donde esta. 'polite' y no 'assertive': no interrumpe a media
          palabra. */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:items-end sm:px-0"
      >
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const Icono = ICONOS[toast.tipo];
            return (
              <motion.div
                key={toast.id}
                // Sin desplazamiento cuando el sistema pide menos movimiento: para
                // algunas personas una animacion que entra de lado es mareo real.
                initial={reduce ? { opacity: 0 } : { opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? { opacity: 0 } : { opacity: 0, y: -8 }}
                transition={{ duration: reduce ? 0.12 : 0.22, ease: [0.16, 1, 0.3, 1] }}
                className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border px-4 py-3 text-sm shadow-lg ${COLORES[toast.tipo]}`}
              >
                <Icono size={18} weight="fill" className={`mt-0.5 shrink-0 ${COLOR_ICONO[toast.tipo]}`} />
                <p className="flex-1 leading-snug">{toast.mensaje}</p>
                <button
                  type="button"
                  onClick={() => descartar(toast.id)}
                  aria-label={cerrarLabel}
                  className="-mr-1 shrink-0 rounded-full p-1 opacity-60 transition-opacity hover:opacity-100"
                >
                  <X size={14} weight="bold" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Contexto.Provider>
  );
}

/**
 * Avisar al cliente. Fuera del proveedor devuelve un no-op en vez de reventar:
 * un aviso que no se puede pintar no debe tumbar la pagina que lo intenta.
 */
export function useToast() {
  const contexto = useContext(Contexto);
  return contexto ?? { mostrar: () => {} };
}
