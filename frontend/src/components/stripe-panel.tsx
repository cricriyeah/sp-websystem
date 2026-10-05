'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { motion, useReducedMotion } from 'motion/react';
import { Lock, ShieldCheck, Ticket, Warning } from '@phosphor-icons/react';
import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckCircle } from '@phosphor-icons/react';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
import { Despliegue } from '@/components/checkout/despliegue';
import { ErrorBlock } from '@/components/error-block';
import { ErrorDeCampo, FieldError, propsDeError } from '@/components/field-error';
import { Turnstile } from '@/components/turnstile';
import { WaitNotice } from '@/components/wait-notice';
import type { Moneda, Pago } from '@/lib/api';

type OrderLine = {
  label: string;
  amount: string;
};

type Phase = 'form' | 'submitting' | 'payment' | 'unavailable' | 'error';

type StripePanelProps = {
  lang: Locale;
  checkout: Dictionary['checkout'];
  waiverAccepted: boolean;
  onWaiverChange: (value: boolean) => void;
  errorWaiver: boolean;
  lines: OrderLine[];
  /** Lo elegido en el viaje (fecha, hora, personas…), vivo desde el paso 1. */
  lineasViaje?: { etiqueta: string; valor: string }[];
  /** En móvil la zona de pago solo se ve al llegar al último paso; en escritorio siempre. */
  pagoVisibleMovil?: boolean;
  total: string;
  amountDueNow: string;
  moneda: Moneda;
  onMonedaChange: (value: Moneda) => void;
  usdDisponible: boolean;
  formaPago: 'completo' | 'anticipo';
  onFormaPagoChange: (value: 'completo' | 'anticipo') => void;
  formaPagoDisponible?: boolean;
  codigoPromocional: string;
  onCodigoPromocionalChange: (value: string) => void;
  codigoPromocionalDisponible?: boolean;
  promoEstado: 'idle' | 'verificando' | 'valido' | 'invalido';
  promoPorcentaje: string | null;
  avisoCargos?: ReactNode;
  etiquetaBotonEnvio?: string;
  submitDisabled?: boolean;
  phase: Phase;
  error: string;
  feedback: Dictionary['feedback'];
  /** Mensaje ya redactado para la vendedora, con la fecha y el grupo del cliente. */
  ayudaMensaje: string;
  onSubmit: () => void;
  /** Token del widget de Turnstile, montado aqui mismo (ver mas abajo). */
  onCaptchaToken: (token: string) => void;
};

function PaymentForm({
  checkout,
  feedback,
  ayudaMensaje,
  etiquetaBotonPago,
  onPagoConfirmado,
  onPagoRechazado,
}: {
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  ayudaMensaje: string;
  etiquetaBotonPago?: string;
  onPagoConfirmado: (procesando: boolean) => void;
  onPagoRechazado?: (mensaje: string, codigo?: string) => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const handleConfirm = async () => {
    if (!stripe || !elements || submitting) return;
    setSubmitting(true);
    setFormError('');

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
      <p className="text-sm text-muted">{checkout.paymentBridge}</p>
      <PaymentElement />

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
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-action px-4 py-3 text-sm font-medium text-action-foreground transition-opacity disabled:opacity-60"
      >
        <Lock size={16} />
        {submitting ? checkout.submitting : (etiquetaBotonPago ?? checkout.confirmPay)}
      </button>
    </div>
  );
}

/** "Es seguro pagar aquí": la duda que queda justo antes de pagar, junto al formulario. */
export function NotaSeguridadStripe({ checkout }: { checkout: Dictionary['checkout'] }) {
  return (
    <p className="mt-4 flex items-start gap-1.5 text-xs leading-relaxed text-muted">
      <ShieldCheck size={14} weight="fill" className="mt-0.5 shrink-0 text-muted" />
      <span>
        {checkout.securityNoteBefore}
        <a
          href="https://stripe.com"
          target="_blank"
          rel="noopener"
          className="text-foreground underline underline-offset-2"
        >
          Stripe
        </a>
        {checkout.securityNoteAfter}
      </span>
    </p>
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
  checkout,
  feedback,
  ayudaMensaje,
  pago,
  encabezadoPago,
  etiquetaBotonPago,
  onPagoConfirmado,
  onPagoRechazado,
}: {
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  ayudaMensaje: string;
  pago: Pick<Pago, 'client_secret' | 'publishable_key'>;
  /** Secuencia de pagos (cruza-empresa): qué ya se hizo, cuál es y cuáles faltan. */
  encabezadoPago?: ReactNode;
  etiquetaBotonPago?: string;
  /** Se llama cuando Stripe acepta el pago; el checkout cambia a la pantalla de
   *  confirmacion. `procesando` es true si el cargo aun no se acredita. */
  onPagoConfirmado: (procesando: boolean) => void;
  onPagoRechazado?: (mensaje: string, codigo?: string) => void;
}) {
  const stripePromise = useMemo(() => loadStripe(pago.publishable_key), [pago.publishable_key]);
  return (
    <>
      <CheckoutSectionCard title={checkout.stepper.payment} estado="activo">
        {encabezadoPago}
        <Elements stripe={stripePromise} options={{ clientSecret: pago.client_secret }}>
          <PaymentForm
            checkout={checkout}
            feedback={feedback}
            ayudaMensaje={ayudaMensaje}
            etiquetaBotonPago={etiquetaBotonPago}
            onPagoConfirmado={onPagoConfirmado}
            onPagoRechazado={onPagoRechazado}
          />
        </Elements>
      </CheckoutSectionCard>
      <NotaSeguridadStripe checkout={checkout} />
    </>
  );
}

export function StripePanel({
  lang,
  checkout,
  waiverAccepted,
  onWaiverChange,
  errorWaiver,
  lines,
  lineasViaje = [],
  pagoVisibleMovil = true,
  total,
  amountDueNow,
  moneda,
  onMonedaChange,
  usdDisponible,
  formaPago,
  onFormaPagoChange,
  formaPagoDisponible = true,
  codigoPromocional,
  onCodigoPromocionalChange,
  codigoPromocionalDisponible = true,
  promoEstado,
  promoPorcentaje,
  avisoCargos,
  etiquetaBotonEnvio,
  submitDisabled = false,
  phase,
  error,
  feedback,
  ayudaMensaje,
  onSubmit,
  onCaptchaToken,
}: StripePanelProps) {
  // Cerrado por default: la mayoria de las reservas no lleva codigo, mismo
  // criterio que la moneda mas abajo — una correccion disponible para quien
  // la busca, no la primera decision del checkout.
  const [promoAbierto, setPromoAbierto] = useState(false);
  const sinMovimiento = useReducedMotion();

  return (
    <CheckoutSectionCard title={checkout.orderSummaryHeadline} variant="elevated">
      {lineasViaje.length > 0 && (
        <dl className="mb-4 flex flex-col gap-2 border-b border-border pb-4">
          {lineasViaje.map((linea) => (
            <div key={linea.etiqueta} className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-muted">{linea.etiqueta}</dt>
              <dd className="text-right text-foreground first-letter:uppercase">{linea.valor}</dd>
            </div>
          ))}
        </dl>
      )}
      <dl className="flex flex-col gap-3">
        {lines.map((line) => (
          <div key={line.label} className="flex items-center justify-between text-sm">
            <dt className="text-muted">{line.label}</dt>
            <dd className="text-foreground">{line.amount}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-5 flex items-center justify-between border-t border-border pt-5">
        <p className="text-sm font-medium text-foreground">{checkout.total}</p>
        <p className="text-lg font-medium tracking-tight text-foreground">{total}</p>
      </div>

      {phase === 'payment' && amountDueNow !== total && (
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className="text-muted">{checkout.amountDueNow}</span>
          <span className="text-foreground">{amountDueNow}</span>
        </div>
      )}

      <div className={pagoVisibleMovil ? undefined : 'hidden lg:block'}>
        {phase !== 'payment' && (
          <p className="mt-6 text-xs font-semibold tracking-wider text-muted uppercase">
            {checkout.howYouPay}
          </p>
        )}

      {/* Ya se precarga segun el idioma (ver checkout-view.tsx): esto deja de
          ser la primera decision del checkout y pasa a ser una correccion
          disponible para quien la busque, junto al total que ya describe. Por
          eso va aqui y no arriba de todo, y por eso es chico. */}
      {usdDisponible && phase !== 'payment' && phase !== 'unavailable' && (
        <fieldset
          className="mt-3 flex items-center justify-between gap-2"
          disabled={phase === 'submitting'}
        >
          <legend className="sr-only">{checkout.currency.headline}</legend>
          <span className="text-xs text-muted">{checkout.currency.headline}</span>
          <div className="flex overflow-hidden rounded-full border border-border text-xs">
            {(['MXN', 'USD'] as const).map((option) => (
              <label
                key={option}
                aria-label={option === 'MXN' ? checkout.currency.mxn : checkout.currency.usd}
                className="cursor-pointer px-2.5 py-1 font-medium text-muted transition-colors has-[:checked]:bg-foreground has-[:checked]:text-surface"
              >
                <input
                  type="radio"
                  name="moneda"
                  checked={moneda === option}
                  onChange={() => onMonedaChange(option)}
                  className="sr-only"
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {formaPagoDisponible !== false && phase !== 'payment' && phase !== 'unavailable' && (
        <fieldset
          className="mt-5 flex flex-col gap-2 border-t border-border pt-5"
          disabled={phase === 'submitting'}
        >
          <legend className="mb-1 text-sm font-medium text-foreground">
            {checkout.paymentMethod.headline}
          </legend>
          {(['completo', 'anticipo'] as const).map((option) => (
            <label
              key={option}
              className="flex items-start gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface"
            >
              <input
                type="radio"
                name="forma-pago"
                checked={formaPago === option}
                onChange={() => onFormaPagoChange(option)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
              />
              <span>
                {option === 'completo'
                  ? checkout.paymentMethod.full
                  : checkout.paymentMethod.deposit}
                {option === 'anticipo' && (
                  <span className="mt-0.5 block text-xs text-muted">
                    {checkout.paymentMethod.depositNote}
                  </span>
                )}
              </span>
            </label>
          ))}

          <div className="mt-1 flex items-center justify-between text-sm">
            <span className="text-muted">{checkout.amountDueNow}</span>
            <span className="text-foreground">{amountDueNow}</span>
          </div>
        </fieldset>
      )}

      {codigoPromocionalDisponible !== false && phase !== 'payment' && phase !== 'unavailable' && (
        <fieldset
          disabled={phase === 'submitting'}
          className={`${formaPagoDisponible ? 'mt-3' : 'mt-5'} border-t border-border pt-3`}
        >
          {/* El botón se pliega mientras el campo se despliega: el panel crece sin
              el salto de cambiar un elemento por otro. Los mensajes de estado
              entran y salen igual, para que el total de abajo no brinque. */}
          <Despliegue abierto={!promoAbierto && !codigoPromocional}>
            <AccionTexto icono={<Ticket size={14} />} onClick={() => setPromoAbierto(true)}>
              {checkout.promoCode.toggle}
            </AccionTexto>
          </Despliegue>
          <Despliegue abierto={promoAbierto || Boolean(codigoPromocional)}>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="codigo-promocional" className="text-xs font-medium text-muted">
                {checkout.promoCode.label}
              </label>
              <input
                id="codigo-promocional"
                type="text"
                value={codigoPromocional}
                disabled={phase === 'submitting'}
                onChange={(e) => onCodigoPromocionalChange(e.target.value)}
                placeholder={checkout.promoCode.placeholder}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
              />
              <Despliegue abierto={promoEstado === 'verificando'}>
                <p className="text-xs text-muted">{checkout.promoCode.checking}</p>
              </Despliegue>
              <Despliegue abierto={promoEstado === 'valido' && Boolean(promoPorcentaje)}>
                <p className="flex items-center gap-1.5 text-xs text-emerald-600">
                  <CheckCircle size={14} weight="fill" />
                  {checkout.promoCode.valid.replace('{percent}', String(Number(promoPorcentaje ?? 0)))}
                </p>
              </Despliegue>
              <Despliegue abierto={promoEstado === 'invalido'}>
                <FieldError id="codigo-promocional-error" mensaje={checkout.promoCode.invalid} />
              </Despliegue>
            </div>
          </Despliegue>
        </fieldset>
      )}

      {phase === 'unavailable' && (
        <div className="mt-6 flex min-h-40 flex-col items-center justify-center gap-2 border border-dashed border-border p-6 text-center">
          <Warning size={20} className="text-muted" />
          <p className="text-sm text-muted">{checkout.paymentUnavailable}</p>
        </div>
      )}

      {phase !== 'payment' && phase !== 'unavailable' && (
        <>
          {/* Deslinde y aviso de privacidad: una linea discreta arriba del
              boton de pagar. Una sola casilla para los dos documentos porque es
              un solo consentimiento del checkout; el texto completo de cada uno
              vive en su propia pagina y abre en otra pestaña para no tirar lo
              que el cliente ya lleno. */}
          {avisoCargos}
          <label className="mt-5 flex items-start gap-2.5 border-t border-border pt-5 text-xs leading-relaxed text-muted">
            <input
              type="checkbox"
              checked={waiverAccepted}
              disabled={phase === 'submitting'}
              onChange={(e) => onWaiverChange(e.target.checked)}
              {...propsDeError('error-waiver', errorWaiver)}
              className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-accent"
            />
            <span>
              {checkout.waiver.accept}{' '}
              <Link
                href={`/${lang}/deslinde`}
                target="_blank"
                rel="noopener"
                className="text-foreground underline underline-offset-2"
              >
                {checkout.waiver.linkLabel}
              </Link>{' '}
              {checkout.waiver.and}{' '}
              <Link
                href={`/${lang}/privacidad`}
                target="_blank"
                rel="noopener"
                className="text-foreground underline underline-offset-2"
              >
                {checkout.waiver.privacyLinkLabel}
              </Link>
              .
            </span>
          </label>
          <ErrorDeCampo id="error-waiver" mensaje={errorWaiver ? checkout.waiver.missing : ''} />

          {/* Mismo lugar donde el cliente ya esta mirando, justo antes de pagar
              — no debajo de la tarjeta, donde parecia parte de otra cosa. */}
          <Turnstile onToken={onCaptchaToken} />

          {phase === 'submitting' && <WaitNotice mensaje={feedback.savingWait} />}

          {phase === 'error' && error && (
            <ErrorBlock
              mensaje={error}
              ayudaTitulo={feedback.helpTitle}
              ayudaCta={feedback.helpCta}
              ayudaMensaje={ayudaMensaje}
            />
          )}

          {/* Es donde de verdad se perdian los clientes: llenaban todo y el
              boton se quedaba igual de quieto que el resto de la tarjeta, sin
              nada que lo distinguiera como "esto es lo que sigue". Mismo pulso
              que booking-bar (color, timing, se apaga solo tras 2 vueltas,
              fallback de opacidad con movimiento reducido), disparado por
              `waiverAccepted`: es lo unico que el cliente tiene que decidir
              activamente antes de que este boton sirva de algo — nombre,
              telefono y correo ya quedaron confirmados en el paso 2. */}
          <motion.button
            type="button"
            onClick={onSubmit}
            disabled={phase === 'submitting' || submitDisabled}
            animate={
              waiverAccepted && phase !== 'submitting' && !submitDisabled && !sinMovimiento
                ? {
                    scale: [1, 1.045, 1],
                    boxShadow: [
                      '0 0 0 0 rgba(255,222,0,0)',
                      '0 0 0 10px rgba(255,222,0,0.28)',
                      '0 0 0 0 rgba(255,222,0,0)',
                    ],
                  }
                : { scale: 1, boxShadow: '0 0 0 0 rgba(255,222,0,0)' }
            }
            transition={
              waiverAccepted && phase !== 'submitting' && !submitDisabled && !sinMovimiento
                ? { duration: 1.4, repeat: 2, repeatDelay: 0.6, ease: 'easeInOut' }
                : { duration: 0.2 }
            }
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-action px-4 py-3 text-sm font-medium text-action-foreground transition-opacity disabled:opacity-60"
          >
            <Lock size={16} />
            {phase === 'submitting' ? checkout.submitting : (etiquetaBotonEnvio ?? checkout.payButton)}
          </motion.button>
        </>
      )}
      </div>
    </CheckoutSectionCard>
  );
}
