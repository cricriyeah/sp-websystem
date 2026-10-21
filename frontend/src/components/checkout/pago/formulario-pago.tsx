'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { Clock, Lock } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { EsqueletoPago } from '@/components/checkout/pago/esqueleto-pago';
import { NotaSeguridadStripe } from '@/components/checkout/pago/nota-seguridad';
import { AvisoProblema } from '@/components/checkout/aviso-problema';
import { usePublicarAccion } from '@/components/reserva/contexto-barra';
import { useMovil } from '@/components/reserva/use-movil';
import { Button } from '@/components/ui/button';
import { WaitNotice } from '@/components/wait-notice';
import type { Pago } from '@/lib/api';
import { fechaHoraDeVencimiento, horaDeVencimiento } from '@/lib/pendientes-texto';
import { RADIO_PAGO, REGLAS_PAGO, TOKENS_PAGO } from '@/lib/tokens-pago';

// Stripe pinta en un iframe: no hereda las variables CSS ni la fuente del sitio,
// así que se le pasan los mismos valores de la marca (lib/tokens-pago.ts, probado contra globals.css,
// incluida la pila de fuentes del sistema) para que el formulario de tarjeta no parezca de otra marca.
// No se carga ninguna fuente externa: el cuerpo usa la fuente del sistema.
const STRIPE_APARIENCIA = {
  theme: 'stripe' as const,
  variables: {
    ...TOKENS_PAGO,
    borderRadius: RADIO_PAGO,
    fontSizeBase: '16px', // 16 px evita el zoom de iOS al enfocar un campo
    spacingUnit: '5px',
    spacingGridRow: '18px',
  },
  rules: REGLAS_PAGO,
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
  const [errorEsDeTarjeta, setErrorEsDeTarjeta] = useState(false);
  // El esqueleto cubre el hueco del iframe hasta que Stripe termina de pintarlo.
  const [listo, setListo] = useState(false);

  const handleConfirm = async () => {
    if (!stripe || !elements || submitting) return;
    setSubmitting(true);
    setFormError('');
    setErrorEsDeTarjeta(false);

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
      setErrorEsDeTarjeta(confirmError.type === 'card_error');
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

  // En móvil el botón de cobro es el de la barra inferior. Se publica desde aquí, dentro de
  // `<Elements>`, porque solo aquí se puede llamar a `confirmPayment`; manda sobre el botón
  // deshabilitado que la pantalla pone mientras baja este formulario.
  const movil = useMovil();
  usePublicarAccion(movil ? {
    etiqueta: etiquetaBotonPago ?? checkout.confirmPay,
    alPulsar: () => { void handleConfirm(); },
    deshabilitado: !stripe,
    razon: stripe ? undefined : checkout.barra.cargandoPago,
    cargando: submitting,
    etiquetaCargando: checkout.submitting,
  } : null, 'contenido');

  return (
    <div className="flex flex-col gap-4">
      {/* Puente entre los dos envios: sin esto, pasar de "reserva guardada"
          (el toast de exito) a un formulario de tarjeta nuevo se lee como "¿otra
          vez lo mismo?" en vez de "el siguiente paso" — el crear-Reserva y el
          cobro son dos peticiones distintas porque Stripe Elements necesita el
          PaymentIntent para montarse, pero eso es un detalle tecnico que al
          cliente no le toca notar. */}
      <p className="texto-cuerpo">{puente}</p>
      {/* El contenedor reserva la altura del esqueleto hasta `onReady`; el esqueleto va
          superpuesto (hermano del iframe, nunca su ancestro) y se desvanece en 150 ms.
          Mientras Stripe carga, su iframe va a opacidad 0: sus campos a medio pintar asomaban
          por detrás del esqueleto. Solo opacidad: Stripe no tolera transform, filter ni will-change. */}
      <div className={`relative ${listo ? '' : 'min-h-[19rem]'}`}>
        <div className={listo ? 'opacity-100 transition-opacity duration-150 motion-reduce:transition-none' : 'pointer-events-none opacity-0'}>
          <PaymentElement onReady={() => setListo(true)} onLoadError={() => setListo(true)} />
        </div>
        <div
          aria-hidden="true"
          className={`absolute inset-0 overflow-hidden bg-superficie transition-[opacity,visibility] duration-150 motion-reduce:transition-none ${
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
        <AvisoProblema
          checkout={checkout}
          feedback={feedback}
          tipo={errorEsDeTarjeta ? 'tarjeta_rechazada' : 'red'}
          mensaje={formError}
          ayudaMensaje={ayudaMensaje}
          // «Probar otra tarjeta» limpia el aviso y deja el formulario para editar; «reintentar» vuelve a cobrar.
          alAccionar={(clave) => (clave === 'reintentar' ? void handleConfirm() : setFormError(''))}
        />
      )}

      {!movil && (
      <Button
        type="button"
        onClick={handleConfirm}
        disabled={!stripe}
        cargando={submitting}
        etiquetaCargando={checkout.submitting}
        bloque
      >
        <Lock size={20} weight="bold" aria-hidden="true" />
        {etiquetaBotonPago ?? checkout.confirmPay}
      </Button>
      )}
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
   * Solo cuando no es null se muestra «Tu lugar está apartado hasta las 4:32 p. m.».
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
  const horaApartado = horaDeVencimiento(apartadoHasta, lang === 'en' ? 'en-US' : 'es-MX');
  const puente = cuando ? checkout.paymentBridgeUntil.replace('{cuando}', cuando) : checkout.paymentBridge;
  return (
    <>
      <CheckoutSectionCard title={checkout.stepper.pago} estado="activo">
        {encabezadoPago}
        {/* Linea fija del apartado: solo cuando crear-pago devolvio apartado_hasta.
            Con APARTADO_MINUTOS=0 o servicios sin cupo fisico, apartadoHasta es null y no aparece. */}
        {horaApartado && (
          <p className="flex items-center gap-2 texto-pequeno font-semibold text-foreground">
            <Clock size={16} weight="bold" aria-hidden />
            {checkout.apartadoHasta.replace('{hora}', horaApartado)}
          </p>
        )}
        <Elements stripe={stripePromise} options={{ clientSecret: pago.client_secret, locale: lang, appearance: STRIPE_APARIENCIA }}>
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
