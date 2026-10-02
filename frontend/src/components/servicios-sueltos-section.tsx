'use client';

import Link from 'next/link';
import { ArrowRight, Compass, Info } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, ServicioCatalogo } from '@/lib/api';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { hrefDetalleServicio, hrefServicio } from '@/lib/booking-href';

type ServiciosSueltosSectionProps = {
  servicios: ServicioCatalogo[];
  lang: Locale;
  dict: Dictionary['catalog'];
  moneda?: Moneda;
  className?: string;
  mostrarVacio?: boolean;
  sedeSlug?: string;
};

export function ServiciosSueltosSection({
  servicios,
  lang,
  dict,
  moneda = 'MXN',
  className = '',
  mostrarVacio = false,
  sedeSlug,
}: ServiciosSueltosSectionProps) {
  const Heading = mostrarVacio ? 'h2' : 'h3';
  if ((!servicios || servicios.length === 0) && !mostrarVacio) {
    return null;
  }

  return (
    <section className={`${mostrarVacio ? '' : 'mt-16 border-t border-border/70 pt-12'} ${className}`}>
      {/* Encabezado secundario de camino alternativo */}
      <div className="max-w-2xl">
        {!mostrarVacio && <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
          <Compass size={14} className="text-accent" />
          <span>{dict.servicesLabel}</span>
        </div>}
        <Heading className={mostrarVacio ? 'text-4xl text-foreground sm:text-5xl' : 'mt-1.5 text-xl font-bold tracking-tight text-foreground sm:text-2xl'}>
          {mostrarVacio ? dict.servicesLabel : dict.standaloneTitle}
        </Heading>
        <p className="mt-1.5 text-sm text-muted">
          {dict.standaloneSubtitle}
        </p>
      </div>
      {servicios.length === 0 && <p className="mt-6 rounded-xl bg-surface p-6 text-sm text-muted">{dict.servicesComingSoon}</p>}

      {/* Grilla de servicios sueltos (menor peso visual que los paquetes) */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {servicios.map((servicio) => {
          const precio = aMoneda(servicio.precio_base, moneda, servicio.tipo_cambio_usd);

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
                    {servicio.tipo_servicio === 'transporte' ? <span className="text-xs text-muted">{dict.quoteRoute}</span> : <>
                    <span className="text-[11px] text-muted">{dict.fromPrice} </span>
                    <span className="text-base font-bold text-foreground">
                      {formatearPrecio(precio, moneda)}
                    </span>
                    <span className="ml-1 text-[10px] text-muted uppercase">{moneda}</span>
                    </>}
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
                        +{servicio.personalizaciones.length - 3} {dict.moreItems}
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="mt-5 grid gap-2 border-t border-border/50 pt-4">
                <Link
                  href={hrefServicio(servicio, lang, moneda)}
                  className="inline-flex min-h-11 w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-deep"
                >
                  <span>{dict.bookStandalone}</span>
                  <ArrowRight size={13} />
                </Link>
                <Link
                  href={hrefDetalleServicio(servicio, lang, moneda, sedeSlug)}
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-border px-3 py-2 text-sm font-semibold text-accent hover:bg-surface"
                >
                  {dict.learnMore}
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {/* Nota de Cross-sell hacia Paquetes */}
      {servicios.length > 0 && <div className="mt-6 flex items-center gap-3 rounded-xl border border-accent/20 bg-accent/5 p-4 text-xs text-foreground">
        <Info size={18} className="shrink-0 text-accent" weight="fill" />
        <p className="leading-relaxed text-muted">
          {dict.crossSellNotice}
        </p>
      </div>}
    </section>
  );
}
