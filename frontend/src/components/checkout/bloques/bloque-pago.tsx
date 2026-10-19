'use client';

import type { Dispatch, RefObject, SetStateAction } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { FormularioPagoDiferido } from '@/components/checkout/pago/pago-diferido';
import type { OrderLine, StripePanelProps } from '@/components/checkout/pago/tipos';
import { StripePanel } from '@/components/stripe-panel';
import type { Pago } from '@/lib/api';

/*
 * Bloque de pago del servicio suelto. Dos mitades porque el pago vive en dos
 * columnas de `PaginaCheckout`: el resumen del pedido (columna derecha, con el
 * portal de "Cómo pagas") y, en la columna de pasos, el sitio de ese portal
 * más el formulario de tarjeta.
 *
 * Mapa de estado de `checkout-view.tsx` (Task 5.1). TODO el estado sigue
 * viviendo allá: un bloque que se pliega o se remonta no puede perderlo.
 *   - Pago (lo lee/escribe este bloque vía props): moneda, formaPago,
 *     waiverAccepted, errorWaiver, codigoPromocional, promoEstado,
 *     promoPorcentaje, promoDescuento, pago, apartadoHasta, pagoProcesando,
 *     confirmandoLargo, reservaId, error, captchaKey + captchaToken (ref),
 *     destinoTarjetaPago, refStripePanel, recuperado* (5, solo confirmación).
 *   - Viaje: day, time, people, fechaSalidaManual, sinLugar.
 *   - Contacto: contact, erroresCampo, refPhone/refFullName/refEmail.
 *   - Extras: personalizaciones, erroresPersonalizacion.
 *   - Asistente: actual, editando, ayuda (useAyudaContextual).
 *   - Ciclo de vida: checkoutId (useCheckoutId, sessionStorage), phase.
 *   - Compartido entre pasos: personalizaciones (viaje/extras/precio),
 *     contact (contacto/pago: correo del código promocional y payload),
 *     moneda (viaje/extras/pago), people, phase.
 */

type PropsResumen = Pick<
  StripePanelProps,
  | 'lang'
  | 'checkout'
  | 'waiverAccepted'
  | 'onWaiverChange'
  | 'errorWaiver'
  | 'moneda'
  | 'onMonedaChange'
  | 'usdDisponible'
  | 'formaPago'
  | 'onFormaPagoChange'
  | 'formaPagoDisponible'
  | 'codigoPromocional'
  | 'onCodigoPromocionalChange'
  | 'promoEstado'
  | 'promoPorcentaje'
  | 'phase'
  | 'error'
  | 'feedback'
  | 'lineasViaje'
  | 'estimado'
  | 'sellos'
  | 'destinoTarjeta'
  | 'ayudaMensaje'
  | 'onSubmit'
  | 'onCaptchaToken'
> & {
  /** Para llevar el resumen a la vista al pasar a "Cómo pagas" (traslados no lo usa). */
  refPanel?: RefObject<HTMLDivElement | null>;
  /** El pago ya creado; con él, el resumen muestra lo que el servidor cobra. */
  pago: Pago | null;
  /** Líneas del viaje y los extras mientras todavía no hay pago. */
  lineas: OrderLine[];
  nombreServicio: string | null | undefined;
  currency: Intl.NumberFormat;
  total: number | null;
  montoAhora: number | null;
};

/**
 * Columna del pedido: UN solo `StripePanel` en todo el árbol (montarlo dos
 * veces inicializaría Stripe.js y el widget de Turnstile por duplicado).
 * Quien lo monta le pone `key={captchaKey}` para remontarlo con su widget.
 */
export function BloquePago({
  refPanel,
  pago,
  lineas,
  nombreServicio,
  currency,
  total,
  montoAhora,
  checkout,
  ...panel
}: PropsResumen) {
  return (
    <div ref={refPanel} className="scroll-mt-28">
      <StripePanel
        {...panel}
        checkout={checkout}
        lines={pago ? [{
          label: nombreServicio ?? checkout.total,
          amount: currency.format(Number(pago.precio_total)),
        }] : lineas}
        total={pago ? currency.format(Number(pago.precio_total)) : total === null ? '–' : currency.format(total)}
        amountDueNow={pago ? currency.format(Number(pago.monto_a_cobrar)) : montoAhora === null ? '–' : currency.format(montoAhora)}
      />
    </div>
  );
}

type PropsTarjeta = {
  lang: Locale;
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  ayudaMensaje: string;
  /** `actual === 'pago' || phase !== 'form'`: el sitio del portal "Cómo pagas". */
  mostrarDestino: boolean;
  /** Callback que guarda el nodo del portal en el estado de la vista. */
  destinoRef: Dispatch<SetStateAction<HTMLElement | null>>;
  /** Solo con `phase === 'payment'`: el pago creado al que se le pone la tarjeta. */
  pagoEnCurso: Pago | null;
  /** Solo el servicio suelto aparta cupo: traslados no lo pasa. */
  apartadoHasta?: string | null;
  antesDePagar?: () => Promise<string | null>;
  onPagoConfirmado: (procesando: boolean) => void;
};

/** Columna de pasos: dónde se pinta "Cómo pagas" y, creado el pago, el formulario de tarjeta. */
export function BloqueTarjetaPago({
  lang,
  checkout,
  feedback,
  ayudaMensaje,
  mostrarDestino,
  destinoRef,
  pagoEnCurso,
  apartadoHasta,
  antesDePagar,
  onPagoConfirmado,
}: PropsTarjeta) {
  return (
    <>
      {mostrarDestino && <div ref={destinoRef} />}

      {pagoEnCurso && (
        <FormularioPagoDiferido
          lang={lang}
          checkout={checkout}
          feedback={feedback}
          ayudaMensaje={ayudaMensaje}
          pago={pagoEnCurso}
          apartadoHasta={apartadoHasta}
          antesDePagar={antesDePagar}
          onPagoConfirmado={onPagoConfirmado}
        />
      )}
    </>
  );
}
