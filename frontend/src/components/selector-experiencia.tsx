// frontend/src/components/selector-experiencia.tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ArrowRight, ArrowSquareOut, CalendarCheck, CaretLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { hrefDetalleServicio, hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { esInlineable, type ChipExperiencia } from '@/lib/selector-experiencia';
import { BookingBar } from '@/components/booking-bar';
import { ID_BARRA_PORTADA } from '@/components/sticky-booking-bar';

type SelectorExperienciaProps = {
  lang: Locale;
  sedeSlug: string;
  destacadas: SedeDestacada[];
  paquetes: PaqueteCatalogo[];
  servicios: ServicioCatalogo[];
  moneda: Moneda;
  booking: Dictionary['booking'];
  minDate: string;
  horasDisponibles: string[];
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
const SLUG_PAQUETE_DESTACADO = 'fin-de-semana-la-paz';
const SLUG_SERVICIO_INSTANTANEO = 'pesca-deportiva';

function precioServicioDesde(servicio: ServicioCatalogo, moneda: Moneda): number | null {
  const raw = moneda === 'USD' ? servicio.precio_base_usd : servicio.precio_base;
  const n = raw !== null && raw !== undefined && raw !== '' ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : null;
}

/**
 * Paso 0 de la pagina de sede: picker de EXACTAMENTE 2 tarjetas fijas (no un
 * grid dinamico de N `destacadas` — version anterior, rechazada: La Paz solo
 * tenia 1 destacada real y el patron no representaba el catalogo real de 8
 * productos). Orden fijo, cada una con rol distinto:
 * 1. Paquete de mayor margen que incluye pesca deportiva ("Fin de Semana en
 *    La Paz") — destacado primero (anclaje: Thaler & Sunstein 2008), navega
 *    a su checkout.
 * 2. Solo pesca deportiva — la unica opcion con formulario inline hoy.
 *
 * Cada tarjeta declara en su propio cuerpo que pasa al tocarla (icono +
 * etiqueta), no una bandera invisible. Al elegir la reservable, esta MISMA
 * zona se transforma en el `BookingBar` (no se apila debajo de tarjetas que
 * siguen ahi). `ID_BARRA_PORTADA` vive en ese wrapper para que
 * `StickyBookingBar` lo siga vigilando sin cambios.
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
  minDate,
  horasDisponibles,
  verTodoLabel,
  hrefVerTodo,
  precioDesdeLabel,
}: SelectorExperienciaProps) {
  const [vista, setVista] = useState<'elegir' | 'reservando'>('elegir');
  const sinMovimiento = useReducedMotion();

  const paqueteDestacado = paquetes.find((p) => p.slug === SLUG_PAQUETE_DESTACADO);
  const servicioInstantaneo = servicios.find(
    (s) => s.slug === SLUG_SERVICIO_INSTANTANEO && s.empresa_slug === EMPRESA_PESCA_LEGACY,
  );

  if (!paqueteDestacado && !servicioInstantaneo) return null;

  const chipServicio: ChipExperiencia | null = servicioInstantaneo
    ? {
        tipo: 'servicio',
        slug: servicioInstantaneo.slug,
        nombre: servicioInstantaneo.nombre,
        empresaSlug: servicioInstantaneo.empresa_slug,
      }
    : null;

  return (
    <div className="relative z-10 mt-6 w-full max-w-2xl">
      <AnimatePresence mode="wait" initial={false}>
        {vista === 'elegir' ? (
          <motion.div
            key="elegir"
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {paqueteDestacado && (
                <Link
                  href={hrefPaquete(paqueteDestacado, lang, moneda)}
                  className="flex flex-col items-start gap-2 rounded-2xl border border-border bg-background/95 p-4 text-left shadow-[0_10px_28px_rgba(11,36,32,0.10)] transition-transform hover:-translate-y-0.5 active:scale-[0.99]"
                >
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
                    <ArrowSquareOut size={16} />
                    {booking.incluyeHospedaje}
                  </span>
                  <span className="text-base font-semibold text-foreground">{paqueteDestacado.nombre}</span>
                  <span className="text-xs text-muted">
                    {precioDesdeLabel}{' '}
                    {formatearPrecio(calcularPrecioPaquete(paqueteDestacado, moneda).precioFinal, moneda)}
                  </span>
                </Link>
              )}

              {servicioInstantaneo && chipServicio && (
                <article className="flex flex-col items-start gap-3 rounded-2xl border border-accent/40 bg-background p-4 text-left shadow-sm">
                  <span className="text-base font-semibold text-foreground">{servicioInstantaneo.nombre}</span>
                  {precioServicioDesde(servicioInstantaneo, moneda) !== null && <span className="text-xs text-muted">{precioDesdeLabel} {formatearPrecio(precioServicioDesde(servicioInstantaneo, moneda)!, moneda)}</span>}
                  <div className="mt-auto flex w-full flex-wrap gap-2">
                    {esInlineable(chipServicio, sedeSlug, EMPRESA_PESCA_LEGACY) ? (
                      <button type="button" onClick={() => setVista('reservando')} className="inline-flex min-h-11 items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white"><CalendarCheck size={16} />{booking.reservarAqui}</button>
                    ) : (
                      <Link href={hrefServicio(servicioInstantaneo, lang, moneda)} className="inline-flex min-h-11 items-center rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white">{booking.reservarAqui}</Link>
                    )}
                    <Link href={hrefDetalleServicio(servicioInstantaneo, lang, moneda, sedeSlug)} className="inline-flex min-h-11 items-center rounded-full border border-border px-4 py-2 text-sm font-semibold text-accent hover:bg-surface">{booking.verDetalles}</Link>
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
          </motion.div>
        ) : (
          <motion.div
            key="reservando"
            id={ID_BARRA_PORTADA}
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <button
              type="button"
              onClick={() => setVista('elegir')}
              className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-hero-ink-soft transition-colors hover:text-hero-ink"
            >
              <CaretLeft size={14} weight="bold" />
              {booking.elegirOtra}
            </button>
            <BookingBar lang={lang} booking={booking} minDate={minDate} horasDisponibles={horasDisponibles} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
