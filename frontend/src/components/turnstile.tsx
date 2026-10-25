'use client';

import { useEffect, useRef } from 'react';

/**
 * Widget de Cloudflare Turnstile para el checkout.
 *
 * Produce el token que el backend verifica al CREAR la reserva
 * (backend/apps/bookings/captcha.py). En el caso normal no le pide nada al
 * cliente: se resuelve solo y el recuadro solo aparece si Cloudflare decide que
 * hay que preguntar algo.
 *
 * Sin `NEXT_PUBLIC_TURNSTILE_SITE_KEY` no pinta nada y no carga el script. Es el
 * mismo apagado que el backend hace sin su secret: en local el checkout funciona
 * sin llaves.
 */

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? '';

/** Sin llave no hay verificación que esperar (en local el checkout funciona sin ella). */
export const turnstileEncendido = SITE_KEY !== '';
const SCRIPT_URL =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

type TurnstileApi = {
  render: (
    el: HTMLElement,
    opciones: {
      sitekey: string;
      callback: (token: string) => void;
      'expired-callback'?: () => void;
      'error-callback'?: () => void;
      'before-interactive-callback'?: () => void;
      'unsupported-callback'?: () => void;
      'refresh-expired'?: 'auto' | 'manual' | 'never';
      appearance?: 'always' | 'execute' | 'interaction-only';
    },
  ) => string;
  remove: (id: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

/** Carga el script una sola vez aunque se monte mas de un widget. */
let cargando: Promise<void> | null = null;

function cargarScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (cargando) return cargando;

  cargando = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      // Que no quede cacheada una promesa rechazada: si el siguiente intento
      // ocurre con la red ya de vuelta, debe poder reintentar la carga.
      cargando = null;
      reject(new Error('No se pudo cargar Turnstile'));
    };
    document.head.appendChild(script);
  });

  return cargando;
}

/**
 * Lo que el widget le dice al checkout:
 * - `esperando`: aun no responde (o el token vencio y pide uno nuevo). Se resuelve solo.
 * - `visible`: Cloudflare decidio preguntar algo; el cliente tiene que marcar la casilla.
 * - `resuelto`: ya hay token.
 * - `error`: el script no cargo o fallo. El backend falla abierto a proposito, asi que no bloquea.
 */
export type EstadoVerificacion = 'esperando' | 'visible' | 'resuelto' | 'error';

export function Turnstile({
  onToken,
  onEstado,
}: {
  /** Recibe el token, o '' cuando expira y todavia no hay uno nuevo. */
  onToken: (token: string) => void;
  onEstado?: (estado: EstadoVerificacion) => void;
}) {
  const contenedor = useRef<HTMLDivElement>(null);
  // El callback cambia en cada render del padre; guardarlo en un ref evita
  // volver a montar el widget cada vez (lo que reiniciaria el reto). Se
  // actualiza en su propio efecto, no durante el render: React prohibe mutar un
  // ref mientras pinta.
  const alToken = useRef(onToken);
  const alEstado = useRef(onEstado);

  useEffect(() => {
    alToken.current = onToken;
    alEstado.current = onEstado;
  }, [onToken, onEstado]);

  useEffect(() => {
    if (!SITE_KEY || !contenedor.current) return;

    let widgetId: string | undefined;
    let cancelado = false;

    cargarScript()
      .then(() => {
        if (cancelado || !contenedor.current || !window.turnstile) return;
        widgetId = window.turnstile.render(contenedor.current, {
          sitekey: SITE_KEY,
          callback: (token) => {
            alEstado.current?.('resuelto');
            alToken.current(token);
          },
          // Cloudflare decidio preguntar algo: el widget aparece y el cliente tiene que marcarlo.
          'before-interactive-callback': () => alEstado.current?.('visible'),
          'unsupported-callback': () => alEstado.current?.('error'),
          // El token vive 5 minutos y alguien puede tardar mas en el checkout.
          // 'auto' lo renueva solo en vez de dejarlo vencido.
          'refresh-expired': 'auto',
          'expired-callback': () => {
            alEstado.current?.('esperando');
            alToken.current('');
          },
          'error-callback': () => {
            alEstado.current?.('error');
            alToken.current('');
          },
          // Solo se hace visible si Cloudflare decide preguntar algo.
          appearance: 'interaction-only',
        });
      })
      .catch(() => {
        // El backend falla abierto si no puede verificar, asi que un script que
        // no carga no debe dejar al cliente sin poder reservar.
        if (!cancelado) {
          alEstado.current?.('error');
          alToken.current('');
        }
      });

    return () => {
      cancelado = true;
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, []);

  if (!SITE_KEY) return null;

  return <div ref={contenedor} className="flex justify-center empty:hidden" />;
}
