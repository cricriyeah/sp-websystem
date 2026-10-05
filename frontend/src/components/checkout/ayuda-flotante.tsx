'use client';

import { WhatsappLogo, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

/**
 * Salida de emergencia durante el llenado: aparece solo tras varios tropiezos
 * (ver `lib/ayuda-contextual.ts`), flotando en la esquina, sin mover nada de la
 * página. Se puede cerrar y no vuelve en esa visita. Sin número de WhatsApp
 * configurado no pinta nada (mismo criterio que `ErrorBlock`).
 */
export function AyudaFlotante({
  visible,
  etiqueta,
  cerrarLabel,
  mensaje,
  onDescartar,
}: {
  visible: boolean;
  etiqueta: string;
  cerrarLabel: string;
  /** Mensaje ya redactado para la vendedora. */
  mensaje: string;
  onDescartar: () => void;
}) {
  const sinMovimiento = useReducedMotion();
  if (!tieneWhatsapp) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="ayuda-flotante"
          role="complementary"
          aria-label={etiqueta}
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="fixed right-4 bottom-4 z-30 flex items-center rounded-full bg-[#25D366] pl-4 text-sm font-medium text-white shadow-lg"
        >
          <a
            href={whatsappHref(mensaje)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 py-2.5"
          >
            <WhatsappLogo size={18} weight="fill" />
            {etiqueta}
          </a>
          <button
            type="button"
            onClick={onDescartar}
            aria-label={cerrarLabel}
            className="ml-1 flex h-9 w-9 items-center justify-center rounded-full transition-opacity hover:opacity-90"
          >
            <X size={14} weight="bold" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
