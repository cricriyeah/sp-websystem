'use client';

import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CuerpoResumen } from '@/components/checkout/pago/cuerpo-resumen';
import { useRegistrarResumen, type ResumenVivo } from '@/components/reserva/contexto-barra';

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
  cargos,
  notaCargos,
  estimado,
}: ResumenVivo) {
  const resumen = { checkout, lines, lineasViaje, sellos, total, amountDueNow, cargos, notaCargos, estimado };
  useRegistrarResumen(resumen);
  return (
    <div className="max-sm:hidden">
      <CheckoutSectionCard title={checkout.orderSummaryHeadline}>
        <CuerpoResumen {...resumen} />
      </CheckoutSectionCard>
    </div>
  );
}
