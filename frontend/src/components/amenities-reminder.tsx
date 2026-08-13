'use client';

import { useEffect } from 'react';
import { X } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { SolicitudKey } from '@/lib/api';

type AmenitiesReminderProps = {
  checkout: Dictionary['checkout'];
  /** true si todavia no pidio lunch (hay algo que ofrecerle). */
  faltaLunch: boolean;
  lunch: boolean;
  onLunchChange: (valor: boolean) => void;
  precioLunch: string;
  /** Solicitudes que todavia no marca. */
  solicitudesFaltantes: SolicitudKey[];
  solicitudes: Record<SolicitudKey, boolean>;
  onSolicitudChange: (key: SolicitudKey, valor: boolean) => void;
  onContinuar: () => void;
  onCerrar: () => void;
  /** Bloquea los botones mientras se esta creando el pago. */
  enviando: boolean;
};

/**
 * Ultimo recordatorio antes de pagar: "¿seguro que no quieres agregar nada?".
 *
 * No cobra ni guarda nada por si mismo — solo muestra opciones y avisa al
 * checkout cuando el cliente decide seguir. Todo lo que toca la red pasa por
 * `onContinuar`, que el checkout protege contra envios repetidos.
 */
export function AmenitiesReminder({
  checkout,
  faltaLunch,
  lunch,
  onLunchChange,
  precioLunch,
  solicitudesFaltantes,
  solicitudes,
  onSolicitudChange,
  onContinuar,
  onCerrar,
  enviando,
}: AmenitiesReminderProps) {
  useEffect(() => {
    const alTeclear = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !enviando) onCerrar();
    };
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, [enviando, onCerrar]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="amenities-reminder-title"
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

      <div className="relative w-full max-w-md rounded-3xl border border-border bg-surface p-6 shadow-[0_24px_60px_rgba(11,36,32,0.28)] sm:p-8">
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
          className="pr-10 text-lg font-medium tracking-tight text-foreground"
        >
          {checkout.amenitiesModal.headline}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">{checkout.amenitiesModal.body}</p>

        {faltaLunch && (
          <label className="mt-6 flex items-start justify-between gap-3 rounded-xl border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-background">
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

        {solicitudesFaltantes.length > 0 && (
          <div className="mt-6">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-medium text-foreground">{checkout.requestsHeadline}</h3>
              <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-0.5 text-[11px] text-accent">
                {checkout.requestsBadge}
              </span>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              {solicitudesFaltantes.map((key) => (
                <label
                  key={key}
                  className="flex items-start gap-3 rounded-xl border border-dashed border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-solid has-[:checked]:border-accent has-[:checked]:bg-background"
                >
                  <input
                    type="checkbox"
                    checked={solicitudes[key]}
                    disabled={enviando}
                    onChange={(e) => onSolicitudChange(key, e.target.checked)}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                  />
                  <span>{checkout.amenities[key]}</span>
                </label>
              ))}
            </div>
          </div>
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
      </div>
    </div>
  );
}
