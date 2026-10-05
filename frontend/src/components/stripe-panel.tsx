'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { motion, useReducedMotion } from 'motion/react';
import { Lock, ShieldCheck, Ticket, Warning } from '@phosphor-icons/react';
import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckCircle } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { BloqueDePaso, CheckoutSectionCard } from '@/components/checkout-section-card';
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
  /**
   * Dónde se pinta la tarjeta "Cómo pagas" (moneda, modalidad, promo, deslinde y
   * el botón que crea el pago): en la columna de pasos, como el cuarto paso. El
   * panel conserva todo el estado y las props; solo el DOM de esa tarjeta vive
   * en otra columna (portal). `null` = todavía no se llegó al paso 4.
   */
  destinoTarjeta?: HTMLElement | null;
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

export function StripePanel(props: StripePanelProps) {
  const { checkout, lines, lineasViaje = [], total, amountDueNow, destinoTarjeta = null } = props;

  return (
    <>
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

        {/* Solo cuando difiere del total (anticipo): si no, repetiría la cifra. */}
        {amountDueNow !== total && (
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-muted">{checkout.amountDueNow}</span>
            <span className="text-foreground">{amountDueNow}</span>
          </div>
        )}
      </CheckoutSectionCard>

      {destinoTarjeta && createPortal(<TarjetaComoPagas {...props} />, destinoTarjeta)}
    </>
  );
}

/**
 * El cuarto paso antes de que exista el pago: cómo paga el cliente (moneda,
 * modalidad, código promocional), el deslinde y el botón que crea el pago.
 * Vive en la columna de pasos (ver `destinoTarjeta`); al crearse el pago se
 * pliega a un renglón y debajo aparece el formulario de tarjeta (`FormularioPago`).
 */
function TarjetaComoPagas({
  lang,
  checkout,
  waiverAccepted,
  onWaiverChange,
  errorWaiver,
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
  // Cerrado por default: la mayoria de las reservas no lleva codigo — una
  // correccion disponible para quien la busca, no la primera decision.
  const [promoAbierto, setPromoAbierto] = useState(false);
  const sinMovimiento = useReducedMotion();
  const pagoCreado = phase === 'payment';
  const abierta = phase !== 'payment' && phase !== 'unavailable';

  const resumen = [
    moneda,
    formaPagoDisponible !== false
      ? (formaPago === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit)
      : null,
  ].filter(Boolean).join(' · ');

  const cta = abierta ? (
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
      // Es donde de verdad se perdian los clientes: llenaban todo y el boton se
      // quedaba igual de quieto que el resto, sin nada que lo distinguiera como
      // "esto es lo que sigue". El pulso (se apaga solo tras 2 vueltas, con
      // fallback de opacidad en movimiento reducido) lo dispara `waiverAccepted`:
      // es lo unico que el cliente tiene que decidir antes de que sirva.
      className="inline-flex items-center justify-center gap-2 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-opacity disabled:opacity-60"
    >
      <Lock size={16} />
      {phase === 'submitting' ? checkout.submitting : (etiquetaBotonEnvio ?? checkout.payButton)}
    </motion.button>
  ) : undefined;

  return (
    <>
      <CheckoutSectionCard
          title={checkout.howYouPay}
          estado={pagoCreado ? 'completado' : 'activo'}
          resumen={resumen}
          pie={cta}
        >
          {phase === 'unavailable' && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 border border-dashed border-border p-6 text-center">
              <Warning size={20} className="text-muted" />
              <p className="text-sm text-muted">{checkout.paymentUnavailable}</p>
            </div>
          )}

          {abierta && (
            <>
              {/* Ya se precarga segun el idioma: una correccion disponible para
                  quien la busque, chica, no la primera decision del checkout. */}
              {usdDisponible && (
                <fieldset className="flex items-center justify-between gap-2" disabled={phase === 'submitting'}>
                  <legend className="sr-only">{checkout.currency.headline}</legend>
                  <span className="text-sm text-muted">{checkout.currency.headline}</span>
                  <div className="flex overflow-hidden rounded-full border border-border text-xs">
                    {(['MXN', 'USD'] as const).map((option) => (
                      <label
                        key={option}
                        aria-label={option === 'MXN' ? checkout.currency.mxn : checkout.currency.usd}
                        className="cursor-pointer px-3 py-1.5 font-medium text-muted transition-colors has-[:checked]:bg-foreground has-[:checked]:text-surface"
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

              {formaPagoDisponible !== false && (
                <BloqueDePaso titulo={checkout.paymentMethod.headline}>
                  <fieldset className="grid gap-3 sm:grid-cols-2" disabled={phase === 'submitting'}>
                    <legend className="sr-only">{checkout.paymentMethod.headline}</legend>
                    {(['completo', 'anticipo'] as const).map((option) => (
                      <label
                        key={option}
                        className="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface"
                      >
                        <input
                          type="radio"
                          name="forma-pago"
                          checked={formaPago === option}
                          onChange={() => onFormaPagoChange(option)}
                          className="h-4 w-4 shrink-0 accent-accent"
                        />
                        {option === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit}
                      </label>
                    ))}
                  </fieldset>
                  {/* La explicacion del anticipo solo cuando se elige: casi todos
                      pagan completo y no necesitan leerla. */}
                  <Despliegue abierto={formaPago === 'anticipo'}>
                    <p className="text-xs text-muted">{checkout.paymentMethod.depositNote}</p>
                  </Despliegue>
                </BloqueDePaso>
              )}

              {codigoPromocionalDisponible !== false && (
                <fieldset disabled={phase === 'submitting'}>
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

              {avisoCargos}

              {/* Deslinde y aviso de privacidad: una sola casilla para los dos
                  documentos porque es un solo consentimiento; el texto completo de
                  cada uno vive en su pagina y abre en otra pestaña para no tirar lo
                  que el cliente ya lleno. */}
              <div>
                <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted">
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
              </div>

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
            </>
          )}
      </CheckoutSectionCard>
      {abierta && <NotaSeguridadStripe checkout={checkout} />}
    </>
  );
}
