'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { Lock } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { EsqueletoPago } from '@/components/checkout/pago/esqueleto-pago';
import { NotaSeguridadStripe } from '@/components/checkout/pago/nota-seguridad';
import { ErrorBlock } from '@/components/error-block';
import { WaitNotice } from '@/components/wait-notice';
import type { Pago } from '@/lib/api';
import { fechaHoraDeVencimiento } from '@/lib/pendientes-texto';

// Stripe pinta en un iframe: no hereda las variables CSS ni la fuente del sitio,
// así que se le pasan los mismos valores de la paleta (globals.css) para que el
// formulario de tarjeta no parezca de otra marca.
const STRIPE_FUENTES = [
  { cssSrc: 'https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&display=swap' },
];
const STRIPE_APARIENCIA = {
  theme: 'stripe' as const,
  variables: {
    colorPrimary: '#281ab5',
    colorText: '#16171c',
    colorTextSecondary: '#55565f',
    colorBackground: '#ffffff',
    colorDanger: '#c22118',
    fontFamily: '"Instrument Sans", system-ui, sans-serif',
    borderRadius: '8px',
  },
};

function PaymentForm({
  puente,
  checkout,
  feedback,
  ayudaMensaje,
  etiquetaBotonPago,
  antesDePagar,
  onPagoConfirmado,
  onPagoRechazado,
}: {
  /** Lo que une "reserva guardada" con el cobro; con hora si la reserva vence. */
  puente: string;
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  ayudaMensaje: string;
  etiquetaBotonPago?: string;
  /** Renueva el apartado antes de cada cobro. null = seguir; texto = detener y mostrarlo; '' = detener sin texto. */
  antesDePagar?: () => Promise<string | null>;
  onPagoConfirmado: (procesando: boolean) => void;
  onPagoRechazado?: (mensaje: string, codigo?: string) => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  // El esqueleto cubre el hueco del iframe hasta que Stripe termina de pintarlo.
  const [listo, setListo] = useState(false);

  const handleConfirm = async () => {
    if (!stripe || !elements || submitting) return;
    setSubmitting(true);
    setFormError('');

    // Renovacion silenciosa del apartado antes de hablar con Stripe: la hace el
    // componente que conoce la reserva. Si decide que no se cobra (sin cupo, monto
    // distinto, cobro ya en curso) devuelve el texto a mostrar, o '' si ya cambio de pantalla.
    if (antesDePagar) {
      const detener = await antesDePagar();
      if (detener !== null) {
        if (detener) setFormError(detener);
        setSubmitting(false);
        return;
      }
    }

    const { error: confirmError, paymentIntent } = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });

    if (confirmError) {
      setFormError(confirmError.message ?? checkout.errorGeneric);
      setSubmitting(false);
      if (confirmError.type === 'card_error') {
        onPagoRechazado?.(confirmError.message ?? checkout.errorGeneric, confirmError.decline_code ?? confirmError.code);
      }
      return;
    }

    // Quien marca la reserva como pagada es el webhook, no esto: segun el metodo
    // de pago el cargo puede quedar en 'processing' un rato.
    onPagoConfirmado(paymentIntent?.status !== 'succeeded');
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Puente entre los dos envios: sin esto, pasar de "reserva guardada"
          (el toast de exito) a un formulario de tarjeta nuevo se lee como "¿otra
          vez lo mismo?" en vez de "el siguiente paso" — el crear-Reserva y el
          cobro son dos peticiones distintas porque Stripe Elements necesita el
          PaymentIntent para montarse, pero eso es un detalle tecnico que al
          cliente no le toca notar. */}
      <p className="text-sm text-muted">{puente}</p>
      {/* El contenedor reserva la altura del esqueleto hasta `onReady`; el esqueleto va
          superpuesto (hermano del iframe, nunca su ancestro) y se desvanece en 150 ms.
          Nada aqui lleva transform, filter ni will-change: Stripe no los tolera. */}
      <div className={`relative ${listo ? '' : 'min-h-[19rem]'}`}>
        <PaymentElement onReady={() => setListo(true)} onLoadError={() => setListo(true)} />
        <div
          aria-hidden="true"
          className={`absolute inset-0 overflow-hidden bg-background transition-[opacity,visibility] duration-150 motion-reduce:transition-none ${
            listo ? 'invisible opacity-0' : ''
          }`}
        >
          <EsqueletoPago />
        </div>
      </div>

      {/* La espera del banco es la mas larga de todo el flujo y la que mas caro
          sale malinterpretar: si el cliente cree que se rompio y recarga, lo hace
          a media autorizacion. */}
      {submitting && <WaitNotice mensaje={feedback.payingWait} mensajeLento={feedback.paySlow} />}

      {formError && (
        <ErrorBlock
          mensaje={formError}
          ayudaTitulo={feedback.helpTitle}
          ayudaCta={feedback.helpCta}
          ayudaMensaje={ayudaMensaje}
        />
      )}

      <button
        type="button"
        onClick={handleConfirm}
        disabled={!stripe || submitting}
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-action px-5 py-2.5 text-center text-sm font-medium leading-tight text-balance text-action-foreground transition-[opacity,transform] active:scale-[0.98] disabled:opacity-60"
      >
        <Lock size={16} className="shrink-0" />
        {submitting ? checkout.submitting : (etiquetaBotonPago ?? checkout.confirmPay)}
      </button>
    </div>
  );
}

/**
 * El formulario de tarjeta como el cuarto paso: una tarjeta más de la columna
 * de pasos, justo debajo de las respuestas ya dadas, y no al final de un panel
 * largo en la otra columna (donde obligaba a hacer scroll para llegar a los
 * campos y a "Pagar"). El resumen del pedido se queda a la derecha.
 *
 * Los `Elements` de Stripe solo envuelven este formulario; Stripe.js se carga
 * aquí una vez por clave publicable (en cruza-empresa cada empresa tiene la
 * suya y el llamador remonta con `key`).
 */
export function FormularioPago({
  lang,
  checkout,
  feedback,
  ayudaMensaje,
  pago,
  venceEn,
  encabezadoPago,
  etiquetaBotonPago,
  apartadoHasta,
  antesDePagar,
  onPagoConfirmado,
  onPagoRechazado,
}: {
  lang: Locale;
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  ayudaMensaje: string;
  pago: Pick<Pago, 'client_secret' | 'publishable_key'>;
  /** Solo las órdenes de varias empresas se liberan a una hora; el resto no promete plazo. */
  venceEn?: string | null;
  /** Secuencia de pagos (cruza-empresa): qué ya se hizo, cuál es y cuáles faltan. */
  encabezadoPago?: ReactNode;
  etiquetaBotonPago?: string;
  /**
   * ISO 8601 del vencimiento del apartado; null si no hubo apartado.
   * Solo cuando no es null se muestra la linea «Tu lugar está apartado por 15 minutos».
   */
  apartadoHasta?: string | null;
  /**
   * Callback que el componente padre pasa para renovar el apartado ANTES de que
   * Stripe confirme el pago. Se llama en cada clic de «Pagar». Devuelve null para
   * seguir al cobro; un texto para detenerlo y mostrarlo; '' para detenerlo sin texto
   * (el padre ya cambio de pantalla: sin cupo, cobro en curso).
   */
  antesDePagar?: () => Promise<string | null>;
  /** Se llama cuando Stripe acepta el pago; el checkout cambia a la pantalla de
   *  confirmacion. `procesando` es true si el cargo aun no se acredita. */
  onPagoConfirmado: (procesando: boolean) => void;
  onPagoRechazado?: (mensaje: string, codigo?: string) => void;
}) {
  const stripePromise = useMemo(() => loadStripe(pago.publishable_key), [pago.publishable_key]);
  const cuando = fechaHoraDeVencimiento(venceEn, lang === 'en' ? 'en-US' : 'es-MX');
  const puente = cuando ? checkout.paymentBridgeUntil.replace('{cuando}', cuando) : checkout.paymentBridge;
  return (
    <>
      <CheckoutSectionCard title={checkout.stepper.payment} estado="activo">
        {encabezadoPago}
        {/* Linea fija del apartado: solo cuando crear-pago devolvio apartado_hasta.
            Con APARTADO_MINUTOS=0 o servicios sin cupo fisico, apartadoHasta es null y no aparece. */}
        {apartadoHasta && (
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <span aria-hidden="true">🔒</span>
            {checkout.apartadoLinea}
          </p>
        )}
        <Elements stripe={stripePromise} options={{ clientSecret: pago.client_secret, locale: lang, fonts: STRIPE_FUENTES, appearance: STRIPE_APARIENCIA }}>
          <PaymentForm
            puente={puente}
            checkout={checkout}
            feedback={feedback}
            ayudaMensaje={ayudaMensaje}
            etiquetaBotonPago={etiquetaBotonPago}
            antesDePagar={antesDePagar}
            onPagoConfirmado={onPagoConfirmado}
            onPagoRechazado={onPagoRechazado}
          />
        </Elements>
      </CheckoutSectionCard>
      <NotaSeguridadStripe checkout={checkout} />
    </>
  );
}
