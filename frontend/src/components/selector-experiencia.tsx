// frontend/src/components/selector-experiencia.tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ArrowRight, ArrowSquareOut, CalendarCheck, CaretLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { resolverChips, esInlineable } from '@/lib/selector-experiencia';
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
  verTodoLabel: string;
  hrefVerTodo: string;
  precioDesdeLabel: string;
};

const EMPRESA_PESCA_LEGACY = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

function precioServicioDesde(servicio: ServicioCatalogo, moneda: Moneda): number | null {
  const raw = moneda === 'USD' ? servicio.precio_base_usd : servicio.precio_base;
  const n = raw !== null && raw !== undefined && raw !== '' ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : null;
}

/**
 * Paso 0 de la pagina de sede: un picker de tarjetas, no una fila de chips-
 * pastilla (version anterior, rechazada por el dueño — ver derivacion PFD
 * 2026-09-16, R1-R5). Cada tarjeta declara en su propio cuerpo que pasa al
 * tocarla (icono + etiqueta de accion), no una bandera invisible: "Reservar
 * aqui" (icono `CalendarCheck`, acento indigo) para la unica opcion que hoy
 * tiene formulario propio, "Ver detalles" (icono `ArrowSquareOut`, borde
 * neutro) para todo lo demas, que navega igual que siempre.
 *
 * Al elegir la tarjeta reservable, esta MISMA zona se transforma en el
 * `BookingBar` (R4) — no se apila un bloque chico debajo de tarjetas que
 * siguen ahi. `ID_BARRA_PORTADA` vive en ese wrapper para que
 * `StickyBookingBar` lo siga vigilando sin cambios.
 */
export function SelectorExperiencia({
  lang,
  sedeSlug,
  destacadas,
  paquetes,
  servicios,
  moneda,
  booking,
  minDate,
  verTodoLabel,
  hrefVerTodo,
  precioDesdeLabel,
}: SelectorExperienciaProps) {
  const [vista, setVista] = useState<'elegir' | 'reservando'>('elegir');
  const sinMovimiento = useReducedMotion();
  const chips = resolverChips(destacadas, paquetes, servicios);

  if (chips.length === 0) return null;

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
              {chips.map((chip) => {
                const inline = esInlineable(chip, sedeSlug, EMPRESA_PESCA_LEGACY);

                if (inline) {
                  return (
                    <button
                      key={`${chip.tipo}-${chip.slug}`}
                      type="button"
                      onClick={() => setVista('reservando')}
                      className="flex flex-col items-start gap-2 rounded-2xl border border-accent/40 bg-background p-4 text-left shadow-[0_10px_28px_rgba(11,36,32,0.14)] transition-transform hover:-translate-y-0.5 active:scale-[0.99]"
                    >
                      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent">
                        <CalendarCheck size={16} weight="bold" />
                        {booking.reservarAqui}
                      </span>
                      <span className="text-base font-semibold text-foreground">{chip.nombre}</span>
                    </button>
                  );
                }

                const servicio = servicios.find(
                  (s) => s.slug === chip.slug && s.empresa_slug === chip.empresaSlug,
                );
                const paquete = paquetes.find((p) => p.slug === chip.slug);
                const precio = servicio
                  ? precioServicioDesde(servicio, moneda)
                  : paquete
                    ? calcularPrecioPaquete(paquete, moneda).precioFinal
                    : null;
                const href = paquete
                  ? hrefPaquete(paquete, lang, moneda)
                  : hrefServicio(servicio!, lang, moneda);

                return (
                  <Link
                    key={`${chip.tipo}-${chip.slug}`}
                    href={href}
                    className="flex flex-col items-start gap-2 rounded-2xl border border-border bg-background/95 p-4 text-left shadow-[0_10px_28px_rgba(11,36,32,0.10)] transition-transform hover:-translate-y-0.5 active:scale-[0.99]"
                  >
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
                      <ArrowSquareOut size={16} />
                      {booking.verDetalles}
                    </span>
                    <span className="text-base font-semibold text-foreground">{chip.nombre}</span>
                    {precio !== null && (
                      <span className="text-xs text-muted">
                        {precioDesdeLabel} {formatearPrecio(precio, moneda)}
                      </span>
                    )}
                  </Link>
                );
              })}
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
            <BookingBar lang={lang} booking={booking} minDate={minDate} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
