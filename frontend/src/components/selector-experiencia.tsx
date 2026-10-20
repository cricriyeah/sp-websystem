// frontend/src/components/selector-experiencia.tsx
'use client';

import Link from 'next/link';
import { m, useReducedMotion } from 'framer-motion';
import { ArrowRight, ArrowSquareOut } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { hrefDetalleServicio, hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { aMoneda } from '@/lib/moneda';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

type SelectorExperienciaProps = {
  lang: Locale;
  sedeSlug: string;
  destacadas: SedeDestacada[];
  paquetes: PaqueteCatalogo[];
  servicios: ServicioCatalogo[];
  moneda: Moneda;
  booking: Dictionary['booking'];
  verTodoLabel: string;
  hrefVerTodo: string;
  precioDesdeLabel: string;
};

const EMPRESA_PESCA_LEGACY = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

/**
 * Slugs fijos del picker de 2 tarjetas del hero (2026-09-17, derivacion PFD +
 * pedido explicito del dueño: destacar el paquete de mayor margen que
 * incluye pesca deportiva, no listar los 8 productos del catalogo real de
 * La Paz — eso ya vive mejor en las secciones de abajo, ver derivacion IA).
 * Se buscan directo en `paquetes`/`servicios` (catalogo real de la sede), no
 * en `destacadas` (editorial) — si ninguno de los dos existe en el catalogo
 * de la sede, el picker no fuerza nada y no renderiza nada.
 */
const SLUG_PAQUETE_DESTACADO = 'pesca-traslado';
const SLUG_SERVICIO_INSTANTANEO = 'pesca-deportiva';

function precioServicioDesde(servicio: ServicioCatalogo, moneda: Moneda): number | null {
  return aMoneda(servicio.precio_base, moneda, servicio.tipo_cambio_usd);
}

/**
 * Paso 0 de la pagina de sede: picker de EXACTAMENTE 2 tarjetas fijas (no un
 * grid dinamico de N `destacadas` — version anterior, rechazada: La Paz solo
 * tenia 1 destacada real y el patron no representaba el catalogo real de 8
 * productos). Orden fijo, cada una con rol distinto:
 * 1. El paquete de La Paz que incluye pesca deportiva ("Pesca + Traslado",
 *    el único del catálogo real) — destacado primero (anclaje: Thaler & Sunstein 2008), navega
 *    a su checkout.
 * 2. Solo pesca deportiva — navega a su checkout.
 *
 * Cada tarjeta declara en su propio cuerpo que pasa al tocarla (icono +
 * etiqueta), no una bandera invisible.
 */
export function SelectorExperiencia({
  lang,
  sedeSlug,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- picker fijo (2026-09-17): ya no deriva de `destacadas`, prop se conserva por el contrato con SedeHero
  destacadas,
  paquetes,
  servicios,
  moneda,
  booking,
  verTodoLabel,
  hrefVerTodo,
  precioDesdeLabel,
}: SelectorExperienciaProps) {
  const sinMovimiento = useReducedMotion();

  const paqueteDestacado = paquetes.find((p) => p.slug === SLUG_PAQUETE_DESTACADO);
  const servicioInstantaneo = servicios.find(
    (s) => s.slug === SLUG_SERVICIO_INSTANTANEO && s.empresa_slug === EMPRESA_PESCA_LEGACY,
  );

  // Sin las dos tarjetas (hoy, toda sede que no es La Paz) el héroe no se queda sin acción:
  // el mismo botón principal del hub baja a «Qué puedes reservar».
  if (!paqueteDestacado && !servicioInstantaneo) {
    return (
      <Link href={hrefVerTodo} className={cn('mt-8', botonClases({ variante: 'principal' }))}>
        {booking.verQueReservar}
      </Link>
    );
  }


  return (
    <div className="relative z-10 mt-6 w-full max-w-2xl">
        <m.div
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {paqueteDestacado && (
              // Misma forma que la tarjeta de la pesca: nombre, precio y el botón de reservar.
              <article className="flex flex-col items-start gap-3 rounded-card border border-accent/40 bg-superficie p-4 text-left">
                {/* Solo un paquete con noches lleva hospedaje; «Pesca + Traslado» no. */}
                {paqueteDestacado.noches != null && (
                  <span className="inline-flex items-center gap-1.5 text-sm font-medium text-muted">
                    <ArrowSquareOut size={16} />
                    {booking.incluyeHospedaje}
                  </span>
                )}
                <span className="text-base font-semibold text-foreground">{paqueteDestacado.nombre}</span>
                <span className="text-sm text-muted">
                  {precioDesdeLabel}{' '}
                  {formatearPrecio(calcularPrecioPaquete(paqueteDestacado, moneda).precioFinal, moneda)}
                </span>
                <div className="mt-auto flex w-full flex-wrap gap-2">
                  <Link href={hrefPaquete(paqueteDestacado, lang, moneda)} className="inline-flex min-h-11 items-center rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white">{booking.reservarAqui}</Link>
                </div>
              </article>
            )}

            {servicioInstantaneo && (
              <article className="flex flex-col items-start gap-3 rounded-card border border-accent/40 bg-superficie p-4 text-left">
                <span className="text-base font-semibold text-foreground">{servicioInstantaneo.nombre}</span>
                {precioServicioDesde(servicioInstantaneo, moneda) !== null && <span className="text-sm text-muted">{precioDesdeLabel} {formatearPrecio(precioServicioDesde(servicioInstantaneo, moneda)!, moneda)}</span>}
                <div className="mt-auto flex w-full flex-wrap gap-2">
                  <Link href={hrefServicio(servicioInstantaneo, lang, moneda, { sede: sedeSlug })} className="inline-flex min-h-11 items-center rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white">{booking.reservarAqui}</Link>
                  <Link href={hrefDetalleServicio(servicioInstantaneo, lang, moneda, sedeSlug)} className="inline-flex min-h-11 items-center rounded-full border border-border px-4 py-2 text-sm font-semibold text-accent hover:bg-cafe-bruma">{booking.verDetalles}</Link>
                </div>
              </article>
            )}

          </div>

          <Link
            href={hrefVerTodo}
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-hero-ink-soft transition-colors hover:text-hero-ink"
          >
            {verTodoLabel}
            <ArrowRight size={14} />
          </Link>
        </m.div>
    </div>
  );
}
