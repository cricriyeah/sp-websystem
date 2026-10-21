'use client';

import { createPortal } from 'react-dom';
import { ResumenPedido } from '@/components/checkout/pago/resumen-pedido';
import { TarjetaComoPagas } from '@/components/checkout/pago/tarjeta-como-pagas';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';

export function StripePanel(props: StripePanelProps) {
  const { destinoTarjeta = null } = props;

  return (
    <>
      <ResumenPedido {...props} />

      {destinoTarjeta && createPortal(<TarjetaComoPagas {...props} />, destinoTarjeta)}
    </>
  );
}
