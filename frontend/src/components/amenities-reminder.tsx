'use client';

import { useEffect } from 'react';
import { X } from '@phosphor-icons/react';
import { motion, useReducedMotion } from 'motion/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type AmenitiesReminderProps = {
  checkout: Dictionary['checkout'];
  /** true si todavia no pidio lunch (hay algo que ofrecerle). */
  faltaLunch: boolean;
  lunch: boolean;
  onLunchChange: (valor: boolean) => void;
  precioLunch: string;
  onContinuar: () => void;
  onCerrar: () => void;
  /** Bloquea los botones mientras se esta creando el pago. */
  enviando: boolean;
};

/**
 * Ultimo recordatorio antes de pagar: "¿seguro que no quieres agregar el lunch?".
 *
 * No cobra ni guarda nada por si mismo — solo muestra la opcion y avisa al
 * checkout cuando el cliente decide seguir. Todo lo que toca la red pasa por
 * `onContinuar`, que el checkout protege contra envios repetidos.
 */
export function AmenitiesReminder({
  checkout,
  faltaLunch,
  lunch,
  onLunchChange,
  precioLunch,
  onContinuar,
  onCerrar,
  enviando,
}: AmenitiesReminderProps) {
  const sinMovimiento = useReducedMotion();

  useEffect(() => {
    const alTeclear = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !enviando) onCerrar();
    };
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, [enviando, onCerrar]);

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-labelledby="amenities-reminder-title"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/40 p-4 sm:items-center"
    >
      {/* Fondo: cierra al hacer clic fuera, salvo mientras se procesa el pago. */}
      <button
        type="button"
        tabIndex={-1}
        aria-hidden
        onClick={() => !enviando && onCerrar()}
        className="absolute inset-0 cursor-default"
      />

      <motion.div
        initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
        className="relative w-full max-w-md border border-border bg-surface p-6 shadow-[0_24px_60px_rgba(11,36,32,0.28)] sm:p-8"
      >
        <button
          type="button"
          onClick={onCerrar}
          disabled={enviando}
          aria-label={checkout.amenitiesModal.close}
          className="absolute top-5 right-5 flex h-8 w-8 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground disabled:opacity-40"
        >
          <X size={16} />
        </button>

        <h2
          id="amenities-reminder-title"
          className="pr-10 font-sans text-lg font-medium tracking-tight text-foreground"
        >
          {checkout.amenitiesModal.headline}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">{checkout.amenitiesModal.body}</p>

        {faltaLunch && (
          <label className="mt-6 flex items-start justify-between gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-background">
            <span className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={lunch}
                disabled={enviando}
                onChange={(e) => onLunchChange(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
              />
              <span>{checkout.amenities.lunch}</span>
            </span>
            <span className="shrink-0 text-right text-muted">
              {precioLunch}
              <span className="block text-xs">{checkout.lunchPerPerson}</span>
            </span>
          </label>
        )}

        <button
          type="button"
          onClick={onContinuar}
          disabled={enviando}
          className="mt-6 flex w-full items-center justify-center rounded-xl bg-foreground px-4 py-3 text-sm font-medium text-surface transition-opacity disabled:opacity-60"
        >
          {enviando ? checkout.submitting : checkout.amenitiesModal.confirm}
        </button>
        <button
          type="button"
          onClick={onCerrar}
          disabled={enviando}
          className="mt-2 w-full rounded-xl px-4 py-2.5 text-sm text-muted transition-colors hover:text-foreground disabled:opacity-40"
        >
          {checkout.amenitiesModal.back}
        </button>
      </motion.div>
    </motion.div>
  );
}
