import { CheckoutSectionCard } from '@/components/checkout-section-card';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';

/** El resumen vivo del pedido (panel derecho): líneas del viaje, cargos, total y «pagarás ahora» si difiere. */
export function ResumenPedido({
  checkout,
  lines,
  lineasViaje = [],
  total,
  amountDueNow,
  resumenSoloEscritorio = false,
}: Pick<StripePanelProps, 'checkout' | 'lines' | 'lineasViaje' | 'total' | 'amountDueNow' | 'resumenSoloEscritorio'>) {
  return (
    <div className={resumenSoloEscritorio ? 'hidden lg:block' : undefined}>
    <CheckoutSectionCard title={checkout.orderSummaryHeadline}>
      {lineasViaje.length > 0 && (
        <dl className="mb-4 flex flex-col gap-2 border-b border-border pb-4">
          {lineasViaje.map((linea) => (
            <div key={linea.etiqueta} className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-muted">{linea.etiqueta}</dt>
              <dd className="text-right text-foreground first-letter:capitalize">{linea.valor}</dd>
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
    </div>
  );
}
