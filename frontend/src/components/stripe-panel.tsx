'use client';

import { useMemo, useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { Lock, Warning } from '@phosphor-icons/react';
import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { ErrorBlock } from '@/components/error-block';
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
  lines: OrderLine[];
  total: string;
  amountDueNow: string;
  moneda: Moneda;
  onMonedaChange: (value: Moneda) => void;
  usdDisponible: boolean;
  formaPago: 'completo' | 'anticipo';
  onFormaPagoChange: (value: 'completo' | 'anticipo') => void;
  phase: Phase;
  error: string;
  pago: Pago | null;
  feedback: Dictionary['feedback'];
  /** Mensaje ya redactado para la vendedora, con la fecha y el grupo del cliente. */
  ayudaMensaje: string;
  onSubmit: () => void;
  /** Se llama cuando Stripe acepta el pago; el checkout cambia a la pantalla de
   *  confirmacion. `procesando` es true si el cargo aun no se acredita. */
  onPagoConfirmado: (procesando: boolean) => void;
};

function PaymentForm({
  checkout,
  feedback,
  ayudaMensaje,
  onPagoConfirmado,
}: {
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  ayudaMensaje: string;
  onPagoConfirmado: (procesando: boolean) => void;
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
      return;
    }

    // Quien marca la reserva como pagada es el webhook, no esto: segun el metodo
    // de pago el cargo puede quedar en 'processing' un rato.
    onPagoConfirmado(paymentIntent?.status !== 'succeeded');
  };

  return (
    <div className="mt-6 flex flex-col gap-4">
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
        {submitting ? checkout.submitting : checkout.confirmPay}
      </button>
    </div>
  );
}

export function StripePanel({
  lang,
  checkout,
  waiverAccepted,
  onWaiverChange,
  lines,
  total,
  amountDueNow,
  moneda,
  onMonedaChange,
  usdDisponible,
  formaPago,
  onFormaPagoChange,
  phase,
  error,
  pago,
  feedback,
  ayudaMensaje,
  onSubmit,
  onPagoConfirmado,
}: StripePanelProps) {
  const stripePromise = useMemo(() => (pago ? loadStripe(pago.publishable_key) : null), [pago]);

  return (
    <CheckoutSectionCard title={checkout.orderSummaryHeadline} variant="elevated">
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

      {/* Ya se precarga segun el idioma (ver checkout-view.tsx): esto deja de
          ser la primera decision del checkout y pasa a ser una correccion
          disponible para quien la busque, junto al total que ya describe. Por
          eso va aqui y no arriba de todo, y por eso es chico. */}
      {usdDisponible && phase !== 'payment' && phase !== 'unavailable' && (
        <fieldset
          className="mt-2 flex items-center justify-end gap-2"
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

      {phase !== 'payment' && phase !== 'unavailable' && (
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

      {phase === 'unavailable' && (
        <div className="mt-6 flex min-h-40 flex-col items-center justify-center gap-2 border border-dashed border-border p-6 text-center">
          <Warning size={20} className="text-muted" />
          <p className="text-sm text-muted">{checkout.paymentUnavailable}</p>
        </div>
      )}

      {phase === 'payment' && pago && stripePromise && (
        <Elements stripe={stripePromise} options={{ clientSecret: pago.client_secret }}>
          <PaymentForm
            checkout={checkout}
            feedback={feedback}
            ayudaMensaje={ayudaMensaje}
            onPagoConfirmado={onPagoConfirmado}
          />
        </Elements>
      )}

      {phase !== 'payment' && phase !== 'unavailable' && (
        <>
          {/* Deslinde y aviso de privacidad: una linea discreta arriba del
              boton de pagar. Una sola casilla para los dos documentos porque es
              un solo consentimiento del checkout; el texto completo de cada uno
              vive en su propia pagina y abre en otra pestaña para no tirar lo
              que el cliente ya lleno. */}
          <label className="mt-5 flex items-start gap-2.5 border-t border-border pt-5 text-xs leading-relaxed text-muted">
            <input
              type="checkbox"
              checked={waiverAccepted}
              disabled={phase === 'submitting'}
              onChange={(e) => onWaiverChange(e.target.checked)}
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

          {phase === 'submitting' && <WaitNotice mensaje={feedback.savingWait} />}

          {phase === 'error' && error && (
            <ErrorBlock
              mensaje={error}
              ayudaTitulo={feedback.helpTitle}
              ayudaCta={feedback.helpCta}
              ayudaMensaje={ayudaMensaje}
            />
          )}

          <button
            type="button"
            onClick={onSubmit}
            disabled={phase === 'submitting'}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-action px-4 py-3 text-sm font-medium text-action-foreground transition-opacity disabled:opacity-60"
          >
            <Lock size={16} />
            {phase === 'submitting' ? checkout.submitting : checkout.payButton}
          </button>
        </>
      )}
    </CheckoutSectionCard>
  );
}
