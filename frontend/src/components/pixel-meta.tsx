'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { EVENTO_CONSENTIMIENTO, leerConsentimiento } from '@/lib/cookies';

/** Pixel de Meta del sitio (pedido del dueño, 2026-11-06). El id no es secreto: va en cada página. */
const PIXEL_ID = '4735852586639451';

declare global {
  interface Window {
    fbq?: unknown;
  }
}

/**
 * El código base que da Meta, tal cual, con un ajuste antes del `init`: `autoConfig` apagado, sin
 * «eventos automáticos» ni lectura de formularios (el checkout pide nombre, correo y teléfono).
 *
 * Las páginas siguientes las cuenta el propio pixel: escucha `pushState`/`popstate` y manda un
 * `PageView` cada vez que cambia la URL. Un `fbq('track', 'PageView')` a mano después del primero
 * no sirve: fbevents.js solo acepta uno por carga de página. Por eso los pasos del checkout
 * (`?paso=`) también cuentan como páginas vistas.
 */
const CODIGO_BASE = `!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('set','autoConfig',false,'${PIXEL_ID}');
fbq('init','${PIXEL_ID}');
fbq('track','PageView');`;

const suscribir = (avisar: () => void) => {
  window.addEventListener(EVENTO_CONSENTIMIENTO, avisar);
  return () => window.removeEventListener(EVENTO_CONSENTIMIENTO, avisar);
};
const aceptoEnEsteNavegador = () => leerConsentimiento() === 'aceptado';
/** En el servidor no hay decisión: no se carga nada. */
const enElServidor = () => false;

/**
 * Carga el pixel en `<head>`, como pide Meta, solo con las cookies aceptadas (lib/cookies.ts: sin
 * respuesta = no). Si acepta a media página, carga en ese momento. No pinta nada; sin JavaScript no
 * hay forma de aceptar, así que tampoco va la imagen `<noscript>` del código de Meta.
 */
export function PixelMeta() {
  const acepto = useSyncExternalStore(suscribir, aceptoEnEsteNavegador, enElServidor);

  useEffect(() => {
    if (!acepto || window.fbq) return;
    const script = document.createElement('script');
    script.textContent = CODIGO_BASE;
    document.head.appendChild(script);
  }, [acepto]);

  return null;
}
