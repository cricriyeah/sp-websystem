'use client';

import { useMemo, useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from '@stripe/react-stripe-js';
import { CheckCircle, Lock, Warning } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import type { Pago } from '@/lib/api';

type OrderLine = {
  label: string;
  amount: string;
};

type Phase = 'form' | 'submitting' | 'payment' | 'unavailable' | 'error';

type StripePanelProps = {
  checkout: Dictionary['checkout'];
  lines: OrderLine[];
  total: string;
  amountDueNow: string;
  formaPago: 'completo' | 'anticipo';
  onFormaPagoChange: (value: 'completo' | 'anticipo') => void;
  phase: Phase;
  error: string;
  pago: Pago | null;
  onSubmit: () => void;
};

function PaymentForm({ checkout }: { checkout: Dictionary['checkout'] }) {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [formError, setFormError] = useState('');

  const handleConfirm = async () => {
    if (!stripe || !elements) return;
    setSubmitting(true);
    setFormError('');

    const { error: confirmError } = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });

    if (confirmError) {
      setFormError(confirmError.message ?? checkout.errorGeneric);
      setSubmitting(false);
      return;
    }

    setConfirmed(true);
    setSubmitting(false);
  };

  if (confirmed) {
    return (
      <div className="mt-6 flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-background p-6 text-center">
        <CheckCircle size={24} className="text-accent" weight="fill" />
        <p className="text-sm text-foreground">{checkout.notice}</p>
      </div>
    );
  }

  return (
    <div className="mt-6 flex flex-col gap-4">
      <PaymentElement />
      {formError && <p className="text-sm text-red-600">{formError}</p>}
      <button
        type="button"
        onClick={handleConfirm}
        disabled={!stripe || submitting}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 text-sm font-medium text-surface transition-opacity disabled:opacity-60"
      >
        <Lock size={16} />
        {submitting ? checkout.submitting : checkout.confirmPay}
      </button>
    </div>
  );
}

export function StripePanel({
  checkout,
  lines,
  total,
  amountDueNow,
  formaPago,
  onFormaPagoChange,
  phase,
  error,
  pago,
  onSubmit,
}: StripePanelProps) {
  const stripePromise = useMemo(
    () => (pago ? loadStripe(pago.publishable_key) : null),
    [pago]
  );

  return (
    <CheckoutSectionCard step={5} title={checkout.orderSummaryHeadline}>
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

      {phase !== 'payment' && (
        <fieldset className="mt-5 flex flex-col gap-2 border-t border-border pt-5" disabled={phase === 'submitting'}>
          <legend className="mb-1 text-sm font-medium text-foreground">
            {checkout.paymentMethod.headline}
          </legend>
          {(['completo', 'anticipo'] as const).map((option) => (
            <label
              key={option}
              className="flex items-start gap-3 rounded-xl border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-background"
            >
              <input
                type="radio"
                name="forma-pago"
                checked={formaPago === option}
                onChange={() => onFormaPagoChange(option)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
              />
              <span>
                {option === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit}
                {option === 'anticipo' && (
                  <span className="mt-0.5 block text-xs text-muted">{checkout.paymentMethod.depositNote}</span>
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
        <div className="mt-6 flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border p-6 text-center">
          <Warning size={20} className="text-muted" />
          <p className="text-sm text-muted">{checkout.paymentUnavailable}</p>
        </div>
      )}

      {phase === 'payment' && pago && stripePromise && (
        <Elements stripe={stripePromise} options={{ clientSecret: pago.client_secret }}>
          <PaymentForm checkout={checkout} />
        </Elements>
      )}

      {phase !== 'payment' && phase !== 'unavailable' && (
        <>
          {phase === 'error' && error && <p className="mt-4 text-sm text-red-600">{error}</p>}
          <button
            type="button"
            onClick={onSubmit}
            disabled={phase === 'submitting'}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 text-sm font-medium text-surface transition-opacity disabled:opacity-60"
          >
            <Lock size={16} />
            {phase === 'submitting' ? checkout.submitting : checkout.payButton}
          </button>
        </>
      )}
    </CheckoutSectionCard>
  );
}
