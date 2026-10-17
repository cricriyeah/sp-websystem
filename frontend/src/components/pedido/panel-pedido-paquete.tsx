import type { Dispatch } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';
import { ErrorBlock } from '@/components/error-block';
import { StripePanel } from '@/components/stripe-panel';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import type { AccionPedido, EstadoPedido } from '@/lib/pedido-estado';
import type { ResultadoPedido } from '@/lib/pedido-paquete';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { AvisoCargos } from './aviso-cargos';
import type { usePagoPedido } from './use-pago-pedido';
import type { PasoId } from '@/lib/pasos-checkout';

type Props = {
  lang: Locale;
  dict: Dictionary;
  paquete: PaqueteCatalogo;
  motor: 'reserva' | 'orden';
  /** El pedido calculado; null si no se puede calcular (p. ej. falta un precio): entonces solo se avisa. */
  pedido: ResultadoPedido | null;
  cargos: ResultadoPedido['cargos'];
  cantidadCargos: number;
  nombreEmpresa: (slug: string) => string;
  moneda: Moneda;
  formaPago: EstadoPedido['formaPago'];
  conUsd: boolean;
  descuento: number;
  codigoPromocional: string;
  promoEstado: StripePanelProps['promoEstado'];
  promoPorcentaje: string | null;
  lineasViaje: { etiqueta: string; valor: string }[];
  destinoTarjetaPago: HTMLElement | null;
  total: string;
  ahora: string;
  ayudaMensaje: string;
  waiverAccepted: boolean;
  errorWaiver: boolean;
  /** Cambia para remontar el panel con su Turnstile: el token es de un solo uso. */
  captchaKey: number;
  actual: PasoId;
  pago: ReturnType<typeof usePagoPedido>;
  despachar: Dispatch<AccionPedido>;
  onWaiverChange: (valor: boolean) => void;
  onCodigoPromocionalChange: (valor: string) => void;
  onCaptchaToken: (token: string) => void;
  onSubmit: () => void;
};

/**
 * Columna del pedido del paquete (fase de formulario): UN solo `StripePanel`,
 * remontado con `key={captchaKey}`, o el aviso si el pedido no se puede calcular.
 * Sin estado propio: el estado de cobro, el código promocional y el deslinde
 * viven en la vista, así que plegar una tarjeta no pierde nada.
 */
export function PanelPedidoPaquete({
  lang, dict, paquete, motor, pedido, cargos, cantidadCargos, nombreEmpresa, moneda, formaPago, conUsd, descuento,
  codigoPromocional, promoEstado, promoPorcentaje, lineasViaje, destinoTarjetaPago, total, ahora, ayudaMensaje,
  waiverAccepted, errorWaiver, captchaKey, actual, pago, despachar,
  onWaiverChange, onCodigoPromocionalChange, onCaptchaToken, onSubmit,
}: Props) {
  const { checkout, feedback, pedido: textos } = dict;
  return pedido ? (
    <StripePanel
      key={captchaKey}
      lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
      waiverAccepted={waiverAccepted}
      onWaiverChange={onWaiverChange}
      errorWaiver={errorWaiver}
      lines={[
        ...cargos.map((cargo) => ({ label: nombreEmpresa(cargo.empresaSlug),
          amount: formatearPrecio(cantidadCargos === 1 ? pedido.total : cargo.monto, moneda) })),
        ...(descuento > 0
          ? [{
              label: `${checkout.promoCode.discountLabel} (${codigoPromocional.trim().toUpperCase()})`,
              amount: `-${formatearPrecio(descuento, moneda)}`,
            }]
          : []),
      ]}
      lineasViaje={lineasViaje}
      destinoTarjeta={destinoTarjetaPago}
      total={total} amountDueNow={ahora} moneda={moneda}
      onMonedaChange={(valor) => despachar({ tipo: 'moneda', valor })} usdDisponible={conUsd}
      formaPago={formaPago}
      onFormaPagoChange={(valor) => despachar({ tipo: 'formaPago', valor })}
      formaPagoDisponible={paquete.permite_anticipo}
      codigoPromocional={codigoPromocional}
      onCodigoPromocionalChange={onCodigoPromocionalChange}
      codigoPromocionalDisponible={motor === 'reserva'}
      promoEstado={promoEstado} promoPorcentaje={promoPorcentaje}
      submitDisabled={actual !== 'pago'}
      phase={pago.fase === 'enviando' ? 'submitting' : pago.error ? 'error' : 'form'}
      error={pago.error}
      avisoCargos={cantidadCargos > 1 ? (
        <div className="mt-5 border-t border-border pt-5">
          <AvisoCargos dict={dict}
            cargos={cargos.map((cargo) => ({ etiqueta: nombreEmpresa(cargo.empresaSlug), monto: formatearPrecio(cargo.monto, moneda) }))}
            total={total} />
        </div>
      ) : undefined}
      etiquetaBotonEnvio={cantidadCargos > 1
        ? textos.continueToPayment.replace('{total}', String(cantidadCargos)) : undefined}
      onSubmit={onSubmit}
      onCaptchaToken={onCaptchaToken}
    />
  ) : (
    <ErrorBlock mensaje={feedback.error.no_disponible}
      ayudaTitulo={feedback.helpTitle} ayudaCta={feedback.helpCta} ayudaMensaje={ayudaMensaje} />
  );
}
