'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { EVENTO_CONSENTIMIENTO, leerConsentimiento } from '@/lib/cookies';

/**
 * Google Analytics 4 (plan de marketing, 2026-11-11). Apagado mientras `NEXT_PUBLIC_GA_ID` (el «ID de medición»
 * `G-…` que da Google Analytics al crear el flujo web) no esté puesto en Vercel. Como el pixel de Meta
 * (`pixel-meta.tsx`), carga solo con las cookies aceptadas y en ese momento si se aceptan a media página.
 *
 * GA4 cuenta solo las páginas vistas, también los cambios de URL sin recarga (medición mejorada del flujo, que
 * viene encendida). Los eventos de venta los manda `lib/medicion.ts` con `window.gtag`.
 */
const GA_ID = (process.env.NEXT_PUBLIC_GA_ID ?? '').trim();
const FORMATO_ID = /^G-[A-Z0-9]{4,20}$/;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

const suscribir = (avisar: () => void) => {
  window.addEventListener(EVENTO_CONSENTIMIENTO, avisar);
  return () => window.removeEventListener(EVENTO_CONSENTIMIENTO, avisar);
};
const aceptoEnEsteNavegador = () => leerConsentimiento() === 'aceptado';
const enElServidor = () => false;

export function GoogleAnalytics() {
  const acepto = useSyncExternalStore(suscribir, aceptoEnEsteNavegador, enElServidor);

  useEffect(() => {
    if (!acepto || !FORMATO_ID.test(GA_ID) || window.gtag) return;
    window.dataLayer = window.dataLayer ?? [];
    // gtag.js lee la cola `dataLayer` con `arguments`, no con arreglos: así lo da Google.
    window.gtag = function gtag() {
      // eslint-disable-next-line prefer-rest-params
      window.dataLayer!.push(arguments);
    };
    window.gtag('js', new Date());
    window.gtag('config', GA_ID);
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
    document.head.appendChild(script);
  }, [acepto]);

  return null;
}
