'use client';

import { useEffect, useState } from 'react';
import { ArrowRight, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BookingBar } from '@/components/booking-bar';

type StickyBookingBarProps = {
  lang: Locale;
  booking: Dictionary['booking'];
  minDate: string;
};

/** Lo pone el hero en el envoltorio de su barra; es lo que se vigila aqui. */
export const ID_BARRA_PORTADA = 'barra-reserva-portada';

/** Cuanto tiene que haber pasado la barra de la portada antes de sacar esta. */
const MARGEN_APARICION = 120;

/**
 * La barra de reserva otra vez, pegada abajo, cuando la de la portada ya se fue
 * con el scroll.
 *
 * El sitio es una sola pagina larga: quien llega al final leyendo las preguntas
 * frecuentes esta a diez pantallas de la unica forma de reservar. Esto la trae
 * de vuelta sin que tenga que subir.
 *
 * **Aparece por posicion, no por cronometro.** En cada cuadro de scroll se mide
 * donde quedo la barra de la portada: si su borde inferior esta 120px por
 * encima de la ventana, esta se enciende. Estuvo con `IntersectionObserver`, que
 * es mas barato, pero avisa de *cambios* y guardaba el nodo del Hero al montar:
 * bastaba una navegacion que volviera a montar la portada para que se quedara
 * observando un nodo huerfano y la barra ya no volviera a salir. Medir la
 * posicion cada vez no tiene ese estado que se pueda quedar viejo, y el
 * `requestAnimationFrame` deja el costo en una medicion por cuadro.
 *
 * **En movil no se pinta el formulario entero.** Apilado son cuatro renglones,
 * media pantalla de telefono tapada de forma permanente. Ahi va un solo boton
 * que abre el formulario como hoja desde abajo, y al elegir se cierra.
 */
export function StickyBookingBar({ lang, booking, minDate }: StickyBookingBarProps) {
  const [visible, setVisible] = useState(false);
  const [hojaAbierta, setHojaAbierta] = useState(false);
  const sinMovimiento = useReducedMotion();

  useEffect(() => {
    let pendiente = 0;

    const evaluar = () => {
      pendiente = 0;
      // Se busca el elemento en cada vuelta, no una sola vez al montar: una
      // navegacion del cliente a la misma ruta vuelve a montar el Hero, y una
      // referencia guardada al nodo viejo se queda apuntando a algo que ya no
      // esta en el documento — que es como la barra se quedaba sin aparecer
      // despues de subir del todo y volver a bajar.
      const barraPortada = document.getElementById(ID_BARRA_PORTADA);
      if (!barraPortada) return;

      // "Ya paso de largo hacia arriba": su borde de abajo quedo MARGEN px por
      // encima del borde superior de la ventana. Es una comparacion de
      // posicion, no un evento que haya que atrapar en el momento justo, asi
      // que da igual lo rapido que se mueva el scroll o cuantos cuadros se
      // pierdan: la respuesta siempre se recalcula desde cero.
      const paso = barraPortada.getBoundingClientRect().bottom < -MARGEN_APARICION;
      setVisible(paso);
      // Al esconderse la barra, la hoja no puede quedarse abierta y huerfana.
      if (!paso) setHojaAbierta(false);
    };

    // El scroll dispara muy seguido; `requestAnimationFrame` colapsa la rafaga
    // en una sola medicion por cuadro, que es lo maximo que el ojo puede ver.
    const alDesplazar = () => {
      if (!pendiente) pendiente = requestAnimationFrame(evaluar);
    };

    alDesplazar();
    window.addEventListener('scroll', alDesplazar, { passive: true });
    window.addEventListener('resize', alDesplazar);
    return () => {
      window.removeEventListener('scroll', alDesplazar);
      window.removeEventListener('resize', alDesplazar);
      if (pendiente) cancelAnimationFrame(pendiente);
    };
  }, []);

  useEffect(() => {
    if (!hojaAbierta) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setHojaAbierta(false);
    };
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, [hojaAbierta]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="barra-pegada"
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          // `pb` con el area segura: en iPhone la barra de gestos se come los
          // ultimos px y el boton quedaria debajo de ella.
          className="fixed inset-x-0 bottom-0 z-30 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 lg:px-12 print:hidden"
        >
          <div className="mx-auto max-w-6xl">
            {/* Escritorio: el formulario completo, igual que en la portada. */}
            <div className="hidden sm:block">
              <BookingBar lang={lang} booking={booking} minDate={minDate} />
            </div>

            {/* Movil: un boton, y el formulario en una hoja que sube. */}
            <button
              type="button"
              onClick={() => setHojaAbierta(true)}
              className="flex w-full items-center justify-center gap-2 bg-action px-6 py-4 text-sm font-semibold text-action-foreground shadow-[0_18px_44px_rgba(22,23,28,0.22)] active:scale-[0.99] sm:hidden"
            >
              {booking.stickyOpen}
              <ArrowRight size={16} weight="bold" />
            </button>
          </div>

          <AnimatePresence>
            {hojaAbierta && (
              <>
                <motion.div
                  key="fondo-hoja"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  onClick={() => setHojaAbierta(false)}
                  className="fixed inset-0 z-40 bg-[rgba(10,11,14,0.5)] sm:hidden"
                />
                <motion.div
                  key="hoja"
                  role="dialog"
                  aria-modal="true"
                  aria-label={booking.stickyTitle}
                  initial={sinMovimiento ? { opacity: 0 } : { y: '100%' }}
                  animate={sinMovimiento ? { opacity: 1 } : { y: 0 }}
                  exit={sinMovimiento ? { opacity: 0 } : { y: '100%' }}
                  transition={{ type: 'spring', stiffness: 320, damping: 34 }}
                  className="fixed inset-x-0 bottom-0 z-50 bg-surface p-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:hidden"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-base text-foreground">{booking.stickyTitle}</span>
                    <button
                      type="button"
                      onClick={() => setHojaAbierta(false)}
                      aria-label={booking.stickyClose}
                      className="flex h-10 w-10 items-center justify-center border border-border-strong text-foreground"
                    >
                      <X size={18} />
                    </button>
                  </div>
                  <BookingBar lang={lang} booking={booking} minDate={minDate} />
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
