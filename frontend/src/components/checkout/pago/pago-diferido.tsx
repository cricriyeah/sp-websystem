'use client';

import dynamic from 'next/dynamic';
import { EsqueletoPago } from '@/components/checkout/pago/esqueleto-pago';

/**
 * Unico modulo que importa `formulario-pago.tsx` (y de forma dinamica): ahi
 * viven `@stripe/stripe-js` y `@stripe/react-stripe-js`, asi que Stripe sale del
 * chunk inicial de /reservar y /traslados y baja cuando el cliente llega al pago.
 */
export const FormularioPagoDiferido = dynamic(
  () => import('@/components/checkout/pago/formulario-pago').then((m) => m.FormularioPago),
  { ssr: false, loading: () => <EsqueletoPago /> },
);

/** Pide el chunk (y con el, Stripe.js) antes de que haga falta; repetirla no cuesta. */
export const precargarFormularioPago = () => import('@/components/checkout/pago/formulario-pago');
