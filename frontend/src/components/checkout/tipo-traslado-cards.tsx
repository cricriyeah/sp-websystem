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
 *
 * Va en lista y no en tres columnas: dentro de una tarjeta cada columna medía
 * ~170 px y la descripción llegaba cortada con "…", justo lo que el cliente
 * necesita leer para escoger. En fila ocupa el ancho completo y se lee entera.
 */
export function TipoTrasladoCards({ tipos, valor, onChange, textos, precioDesde, desdeLabel = 'Desde', etiqueta }: Props) {
  return (
    <div role="group" aria-label={etiqueta} className="flex flex-col gap-3">
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
            className={`flex items-start gap-4 rounded-lg border p-4 text-left transition-colors ${
              seleccionado
                ? 'border-accent bg-surface ring-1 ring-accent'
                : 'border-border bg-background hover:border-border-strong'
            }`}
          >
            <Icono size={24} className="mt-0.5 shrink-0 text-accent" />
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="text-sm font-semibold leading-tight text-foreground">{info.title}</span>
              <span className="text-xs leading-relaxed text-muted">{info.description}</span>
              {precio && (
                <span className="mt-1 text-xs font-medium text-accent">{desdeLabel} {precio}</span>
              )}
            </span>
            <span className="flex h-6 w-6 shrink-0 items-center justify-center">
              {seleccionado && <Check size={16} weight="bold" className="text-accent" />}
            </span>
          </button>
        );
      })}
    </div>
  );
}
