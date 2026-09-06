'use client';

import Link from 'next/link';
import { ArrowRight, Compass, Info } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, ServicioCatalogo } from '@/lib/api';
import { formatearPrecio } from '@/lib/pricing-paquete';

type ServiciosSueltosSectionProps = {
  servicios: ServicioCatalogo[];
  lang: Locale;
  dict: Dictionary['catalog'];
  moneda?: Moneda;
  className?: string;
};

export function ServiciosSueltosSection({
  servicios,
  lang,
  dict,
  moneda = 'MXN',
  className = '',
}: ServiciosSueltosSectionProps) {
  if (!servicios || servicios.length === 0) {
    return null;
  }

  return (
    <section className={`mt-16 border-t border-border/70 pt-12 sm:mt-24 sm:pt-16 ${className}`}>
      {/* Encabezado secundario de camino alternativo */}
      <div className="max-w-2xl">
        <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
          <Compass size={14} className="text-accent" />
          <span>Servicios Individuales</span>
        </div>
        <h3 className="mt-1.5 text-xl font-bold tracking-tight text-foreground sm:text-2xl">
          {dict.standaloneTitle}
        </h3>
        <p className="mt-1.5 text-sm text-muted">
          {dict.standaloneSubtitle}
        </p>
      </div>

      {/* Grilla de servicios sueltos (menor peso visual que los paquetes) */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {servicios.map((servicio) => {
          const precioRaw =
            moneda === 'USD' && servicio.precio_base_usd
              ? servicio.precio_base_usd
              : servicio.precio_base;
          const precio = parseFloat(precioRaw) || 0;

          return (
            <div
              key={servicio.id}
              className="flex flex-col justify-between rounded-xl border border-border bg-card p-5 transition-all hover:border-accent/40 hover:shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="rounded-md bg-muted/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-muted">
                    {servicio.tipo_servicio.replace('_', ' ')}
                  </span>
                  <div className="text-right">
                    <span className="text-[11px] text-muted">{dict.fromPrice} </span>
                    <span className="text-base font-bold text-foreground">
                      {formatearPrecio(precio, moneda)}
                    </span>
                    <span className="ml-1 text-[10px] text-muted uppercase">{moneda}</span>
                  </div>
                </div>

                <h4 className="mt-3 text-base font-semibold text-foreground">
                  {servicio.nombre}
                </h4>

                {servicio.descripcion && (
                  <p className="mt-1.5 text-xs leading-relaxed text-muted line-clamp-2">
                    {servicio.descripcion}
                  </p>
                )}

                {servicio.personalizaciones && servicio.personalizaciones.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {servicio.personalizaciones.slice(0, 3).map((p) => (
                      <span
                        key={p.id}
                        className="rounded bg-background px-1.5 py-0.5 text-[10px] text-muted border border-border/60"
                      >
                        +{p.nombre}
                      </span>
                    ))}
                    {servicio.personalizaciones.length > 3 && (
                      <span className="text-[10px] text-muted self-center">
                        +{servicio.personalizaciones.length - 3} más
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="mt-5 border-t border-border/50 pt-4">
                <Link
                  href={`/${lang}/reservar?servicio=${servicio.slug}&moneda=${moneda}`}
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground transition-colors hover:border-accent hover:text-accent"
                >
                  <span>{dict.bookStandalone}</span>
                  <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {/* Nota de Cross-sell hacia Paquetes */}
      <div className="mt-6 flex items-center gap-3 rounded-xl border border-accent/20 bg-accent/5 p-4 text-xs text-foreground">
        <Info size={18} className="shrink-0 text-accent" weight="fill" />
        <p className="leading-relaxed text-muted">
          {dict.crossSellNotice}
        </p>
      </div>
    </section>
  );
}
