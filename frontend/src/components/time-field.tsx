'use client';

import { Check, Clock } from '@phosphor-icons/react';
import { FieldPopover } from '@/components/field-popover';
import { formatHour, TOUR_HOURS } from '@/lib/dates';

type TimeFieldProps = {
  label: string;
  help: string;
  value: string;
  onChange: (time: string) => void;
};

export function TimeField({ label, help, value, onChange }: TimeFieldProps) {
  return (
    <FieldPopover
      label={label}
      value={formatHour(value)}
      icon={<Clock size={20} className="shrink-0 text-muted" />}
      // Ayuda + las 9 salidas de la ventana de 5 a 7 am.
      alturaEstimada={400}
    >
      {(cerrar) => (
        <div className="w-56">
          <p className="px-1 pb-2 text-xs text-muted">{help}</p>
          {/* La ventana de salida es de 5 a 7 am en pasos de 15 minutos: caben
              las 9 opciones sin scroll, no hace falta virtualizar nada. */}
          <ul className="flex flex-col gap-0.5">
            {TOUR_HOURS.map((hora) => {
              const seleccionada = hora === value;
              return (
                <li key={hora}>
                  <button
                    type="button"
                    aria-pressed={seleccionada}
                    onClick={() => {
                      onChange(hora);
                      cerrar();
                    }}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                      seleccionada
                        ? 'bg-accent font-medium text-accent-foreground'
                        : 'text-foreground hover:bg-background'
                    }`}
                  >
                    {formatHour(hora)}
                    {seleccionada && <Check size={14} weight="bold" />}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </FieldPopover>
  );
}
