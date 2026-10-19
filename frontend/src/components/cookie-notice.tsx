'use client';

import { useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { guardarConsentimiento, leerConsentimiento } from '@/lib/cookies';
import { Button } from '@/components/ui/button';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';

/**
 * Aviso de cookies.
 *
 * Tres decisiones que no son de estilo:
 *
 * - **Aceptar y rechazar pesan igual.** Un "rechazar" escondido como texto gris
 *   mientras "aceptar" es un boton de color es un patron oscuro, y aqui ademas
 *   seria contraproducente: el cliente que siente que lo empujaron llega al
 *   formulario de pago con la guardia arriba, en la pantalla donde va a teclear
 *   una tarjeta.
 * - **Abajo, no en medio.** Un modal que tapa la portada gasta la primera
 *   impresion —los 50 ms donde se decide si el sitio parece serio— en un
 *   tramite. Abajo se ve, no bloquea, y se contesta cuando el cliente quiera.
 * - **No aparece en la primera pintada.** En el servidor no hay forma de saber si
 *   este cliente ya respondio, asi que ahi se asume que si: pintar el aviso y
 *   quitarlo al hidratar le daria un parpadeo a todo el que ya contesto. La
 *   decision vive en localStorage —un almacen externo a React— y por eso se lee
 *   con `useSyncExternalStore` y no con un efecto que llame a setState.
 */

/** localStorage no avisa de sus propios cambios: aqui no hay a que suscribirse. */
const sinCambios = () => () => {};

const yaRespondioEnEsteNavegador = () => leerConsentimiento() !== undefined;

/** En el servidor: no pintar nada. Ver la nota de arriba sobre el parpadeo. */
const enElServidor = () => true;

/**
 * `/reservar` y `/traslados`: el aviso es fijo abajo y la barra del checkout lo taparía sin dejar
 * contestarlo. Ahí no carga nada no esencial (no hay analítica ni pixel), así que no se pregunta.
 */
const RUTA_RESERVA = /^\/[a-z]{2}\/(reservar|traslados)(\/|$)/;
export function CookieNotice({
  lang,
  cookies,
}: {
  lang: Locale;
  cookies: Dictionary['cookies'];
}) {
  const yaRespondio = useSyncExternalStore(
    sinCambios,
    yaRespondioEnEsteNavegador,
    enElServidor,
  );
  // El almacen no notifica, asi que la respuesta de ahorita se recuerda aparte.
  const [respondioAhora, setRespondioAhora] = useState(false);
  const sinMovimiento = useReducedMotion();
  const enReserva = RUTA_RESERVA.test(usePathname() ?? '');

  const visible = !yaRespondio && !respondioAhora && !enReserva;

  const responder = (decision: 'aceptado' | 'rechazado') => {
    guardarConsentimiento(decision);
    setRespondioAhora(true);
  };

  return (
    <AnimatePresence>
      {visible && (
        <m.div
          // AnimatePresence necesita una key estable para saber que este hijo se
          // fue; sin ella el aviso se queda pintado despues de responder.
          key="aviso-cookies"
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.25 }}
          // z-40: por encima de la pagina, por debajo de los avisos y del modal
          // de amenidades (z-50), que si exigen respuesta.
          className="fixed inset-x-0 bottom-0 z-40 px-4 pb-4"
          role="region"
          aria-label={cookies.title}
        >
          <div className="mx-auto flex max-w-3xl flex-col gap-4 rounded-card border border-border bg-superficie p-5 shadow-n2 sm:flex-row sm:items-center sm:gap-6">
            <p className="text-sm text-foreground">
              {cookies.body}{' '}
              <Link
                href={`/${lang}/privacidad`}
                className="underline underline-offset-2 transition-colors hover:text-accent"
              >
                {cookies.more}
              </Link>
            </p>

            <div className="flex shrink-0 gap-2">
              {/* F3 conserva el aspecto de hoy: los className sustituyen lo que la variante
                  trae de la marca nueva (fondo blanco, borde fuerte, amarillo de accion).
                  F7 los quita cuando la variante ya pinte esto por si sola. */}
              <Button
                variante="secundario"
                onClick={() => responder('rechazado')}
              >
                {cookies.reject}
              </Button>
              <Button
                variante="principal"
                onClick={() => responder('aceptado')}
              >
                {cookies.accept}
              </Button>
            </div>
          </div>
        </m.div>
      )}
    </AnimatePresence>
  );
}
