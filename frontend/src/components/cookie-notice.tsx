'use client';

import { useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { guardarConsentimiento, leerConsentimiento } from '@/lib/cookies';
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

  const visible = !yaRespondio && !respondioAhora;

  const responder = (decision: 'aceptado' | 'rechazado') => {
    guardarConsentimiento(decision);
    setRespondioAhora(true);
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
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
          <div className="mx-auto flex max-w-3xl flex-col gap-4 rounded-2xl border border-border bg-surface p-5 shadow-[0_18px_45px_rgba(11,36,32,0.16)] sm:flex-row sm:items-center sm:gap-6">
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
              <button
                type="button"
                onClick={() => responder('rechazado')}
                className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground transition-transform active:scale-[0.98]"
              >
                {cookies.reject}
              </button>
              <button
                type="button"
                onClick={() => responder('aceptado')}
                className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition-transform active:scale-[0.98]"
              >
                {cookies.accept}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
