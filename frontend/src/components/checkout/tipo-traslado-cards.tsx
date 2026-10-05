'use client';

import { AirplaneLanding, AirplaneTakeoff, Car, Check } from '@phosphor-icons/react';
import type { TipoTraslado } from '@/lib/api';

const ICONOS: Record<TipoTraslado, typeof Car> = {
  redondo_aeropuerto: AirplaneTakeoff,
  redondo_actividad: Car,
  recepcion_aeropuerto: AirplaneLanding,
};

type Props = {
  tipos: TipoTraslado[];
  valor: TipoTraslado;
  onChange: (tipo: TipoTraslado) => void;
  textos: Record<TipoTraslado, { title: string; description: string }>;
  /** Solo el checkout de traslados cotiza por tipo; en el paquete el traslado va incluido. */
  precioDesde?: (tipo: TipoTraslado) => string | null;
  /** Texto del "Desde {precio}", ya traducido. */
  desdeLabel?: string;
  /** Nombre accesible del grupo (la pregunta). */
  etiqueta?: string;
};

/**
 * La decisión "qué tipo de traslado" se ve igual en `/traslados` y dentro de un
 * paquete: una sola pieza para las dos, para que el cliente no tenga que
 * reaprender una pregunta que ya contestó en otro lado.
 */
export function TipoTrasladoCards({ tipos, valor, onChange, textos, precioDesde, desdeLabel = 'Desde', etiqueta }: Props) {
  return (
    <div role="group" aria-label={etiqueta} className="grid gap-3 sm:grid-cols-3">
      {tipos.map((tipo) => {
        const seleccionado = valor === tipo;
        const info = textos[tipo];
        const Icono = ICONOS[tipo];
        const precio = precioDesde?.(tipo) ?? null;
        return (
          <button
            key={tipo}
            type="button"
            aria-pressed={seleccionado}
            onClick={() => onChange(tipo)}
            className={`flex flex-col items-start justify-between rounded-xl border p-4 text-left transition-colors ${
              seleccionado
                ? 'border-accent bg-surface shadow-sm ring-1 ring-accent'
                : 'border-border bg-background hover:border-border-strong'
            }`}
          >
            <div className="flex w-full items-center justify-between">
              <Icono size={24} className="text-accent" />
              {seleccionado && <Check size={16} weight="bold" className="text-accent" />}
            </div>
            <span className="mt-3 font-semibold text-foreground text-sm leading-tight">
              {info.title}
            </span>
            <span className="mt-1 text-xs text-muted leading-relaxed line-clamp-3">
              {info.description}
            </span>
            {precio && (
              <span className="mt-4 inline-block text-xs font-medium text-accent">
                {desdeLabel} {precio}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
