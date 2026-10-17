import { ShieldCheck } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

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
