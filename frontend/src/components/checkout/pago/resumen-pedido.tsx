'use client';

import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CuerpoResumen } from '@/components/checkout/pago/cuerpo-resumen';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';
import { useRegistrarResumen } from '@/components/reserva/contexto-barra';

/**
 * El resumen vivo del pedido (panel derecho). En móvil no se ve: lo reemplaza la hoja «Ver resumen»
 * de la barra inferior, que pinta este mismo contenido; el panel solo lo publica para ella.
 */
export function ResumenPedido({
  checkout,
  lines,
  lineasViaje = [],
  sellos = [],
  total,
  amountDueNow,
}: Pick<StripePanelProps, 'checkout' | 'lines' | 'lineasViaje' | 'sellos' | 'total' | 'amountDueNow'>) {
  useRegistrarResumen({ checkout, lines, lineasViaje, sellos, total, amountDueNow });
  return (
    <div className="max-sm:hidden">
      <CheckoutSectionCard title={checkout.orderSummaryHeadline}>
        <CuerpoResumen checkout={checkout} lines={lines} lineasViaje={lineasViaje} sellos={sellos} total={total} amountDueNow={amountDueNow} />
      </CheckoutSectionCard>
    </div>
  );
}
