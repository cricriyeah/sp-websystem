'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Check,
  Lock,
  MinusCircle,
  Sparkle,
  Tag,
} from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';

type PaqueteCardProps = {
  paquete: PaqueteCatalogo;
  lang: Locale;
  dict: Dictionary['catalog'];
  moneda?: Moneda;
  className?: string;
  onSelect?: (
    paquete: PaqueteCatalogo,
    serviciosExcluidos: number[],
    precioFinal: number,
  ) => void;
};

export function PaqueteCard({
  paquete,
  lang,
  dict,
  moneda = 'MXN',
  className = '',
  onSelect,
}: PaqueteCardProps) {
  // IDs de servicios que el usuario ha desmarcado in-place
  const [serviciosExcluidos, setServiciosExcluidos] = useState<number[]>([]);

  // Cálculo reactivo puro del precio ancla ajustado
  const calculo = calcularPrecioPaquete(paquete, serviciosExcluidos, moneda);

  const tieneAjuste = calculo.totalAjustesDescontados > 0;
  const totalServicios = paquete.servicios_asociados.length;

  function toggleServicio(servicioId: number, removible: boolean) {
    if (!removible) return;
    setServiciosExcluidos((prev) =>
      prev.includes(servicioId)
        ? prev.filter((id) => id !== servicioId)
        : [...prev, servicioId],
    );
  }

  // URL para continuar hacia el checkout con este paquete y los componentes elegidos
  const bookingHref = `/${lang}/reservar?paquete=${paquete.slug}${
    serviciosExcluidos.length > 0 ? `&excluidos=${serviciosExcluidos.join(',')}` : ''
  }&moneda=${moneda}`;

  return (
    <article
      className={`relative flex flex-col justify-between overflow-hidden rounded-2xl border-2 border-accent/40 bg-surface p-6 sm:p-8 shadow-[0_12px_40px_rgba(11,36,32,0.12)] transition-shadow hover:shadow-[0_18px_48px_rgba(11,36,32,0.18)] ${className}`}
    >
      {/* Badge superior de producto dominante (Perception-First Design) */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 pb-4">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-accent/15 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-accent">
          <Sparkle size={13} weight="fill" />
          <span>{dict.featuredBadge}</span>
        </div>
        <div className="text-xs font-medium text-muted">
          {paquete.sede} • {paquete.empresa_lider}
        </div>
      </div>

      {/* Título y descripción de la experiencia */}
      <div className="pt-5">
        <h3 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          {paquete.nombre}
        </h3>
        {paquete.descripcion && (
          <p className="mt-2 text-sm leading-relaxed text-muted sm:text-[15px]">
            {paquete.descripcion}
          </p>
        )}
      </div>

      {/* Bloque de Precio Ancla editable */}
      <div className="mt-6 rounded-xl border border-border/80 bg-background/70 p-4 sm:p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <span className="text-xs font-medium uppercase tracking-wider text-muted">
              {tieneAjuste ? dict.adjustedPrice : dict.anchorPrice}
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-foreground sm:text-4xl">
                {formatearPrecio(calculo.precioFinal, moneda)}
              </span>
              <span className="text-xs font-semibold text-muted uppercase">{moneda}</span>
            </div>
          </div>

          {tieneAjuste && (
            <div className="text-right">
              <span className="text-xs text-muted line-through">
                {formatearPrecio(calculo.precioAncla, moneda)}
              </span>
              <div className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                <Tag size={12} weight="bold" />
                <span>
                  -{formatearPrecio(calculo.totalAjustesDescontados, moneda)} {dict.discountApplied}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Desglose de componentes con edición in-place */}
      <div className="mt-6 flex-1">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-foreground">
            {dict.servicesIncluded} ({calculo.serviciosActivosCount}/{totalServicios})
          </h4>
          <span className="text-xs text-muted">
            {paquete.servicios_asociados.some((s) => s.removible) && dict.removableNotice}
          </span>
        </div>

        <div className="mt-3 space-y-2.5">
          {paquete.servicios_asociados.map((item) => {
            const sId = item.servicio?.id ?? item.servicio_id;
            const estaExcluido = serviciosExcluidos.includes(sId);
            const servicioNombre = item.servicio?.nombre ?? 'Servicio incluido';
            const servicioDesc = item.servicio?.descripcion;
            const ajusteRaw =
              moneda === 'USD' && item.ajuste_precio_usd
                ? item.ajuste_precio_usd
                : item.ajuste_precio;
            const ajusteMonto = parseFloat(ajusteRaw) || 0;

            return (
              <div
                key={item.id}
                onClick={() => toggleServicio(sId, item.removible)}
                className={`flex items-start justify-between gap-3 rounded-xl border p-3.5 transition-colors ${
                  item.removible ? 'cursor-pointer' : 'cursor-default'
                } ${
                  estaExcluido
                    ? 'border-dashed border-border bg-muted/5 opacity-70'
                    : 'border-border bg-card hover:border-accent/50'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
                      estaExcluido
                        ? 'border-muted text-transparent'
                        : item.removible
                        ? 'border-accent bg-accent text-white'
                        : 'border-accent/50 bg-accent/20 text-accent'
                    }`}
                  >
                    {estaExcluido ? (
                      <MinusCircle size={14} className="text-muted" />
                    ) : item.removible ? (
                      <Check size={13} weight="bold" />
                    ) : (
                      <Lock size={12} weight="bold" />
                    )}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm font-medium ${
                          estaExcluido
                            ? 'text-muted line-through'
                            : 'text-foreground font-semibold'
                        }`}
                      >
                        {servicioNombre}
                      </span>
                      {!item.removible && (
                        <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-semibold text-accent uppercase tracking-wider">
                          {dict.fixedService}
                        </span>
                      )}
                    </div>
                    {servicioDesc && (
                      <p className="mt-0.5 text-xs text-muted line-clamp-2">{servicioDesc}</p>
                    )}
                  </div>
                </div>

                {item.removible && ajusteMonto > 0 && (
                  <div className="shrink-0 text-right">
                    <span
                      className={`text-xs font-medium ${
                        estaExcluido ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : 'text-muted'
                      }`}
                    >
                      {estaExcluido ? `-${formatearPrecio(ajusteMonto, moneda)}` : `Ahorra ${formatearPrecio(ajusteMonto, moneda)}`}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Botón de acción principal hacia Checkout */}
      <div className="mt-8 border-t border-border/70 pt-6">
        {onSelect ? (
          <button
            type="button"
            onClick={() => onSelect(paquete, serviciosExcluidos, calculo.precioFinal)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-5 py-3.5 text-sm font-semibold text-white shadow-md transition-transform hover:brightness-105 active:scale-[0.99]"
          >
            <span>{dict.bookPackage}</span>
            <ArrowRight size={16} weight="bold" />
          </button>
        ) : (
          <Link
            href={bookingHref}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-5 py-3.5 text-sm font-semibold text-white shadow-md transition-transform hover:brightness-105 active:scale-[0.99]"
          >
            <span>{dict.bookPackage}</span>
            <ArrowRight size={16} weight="bold" />
          </Link>
        )}
      </div>
    </article>
  );
}
