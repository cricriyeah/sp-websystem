import type { ComponentProps } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutStepper } from '@/components/checkout-stepper';
import type { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { SiteHeader } from '@/components/site-header';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { claveMotivoRechazo, ofreceAyuda, pagosRetenidosAntes } from '@/lib/fallo-pago';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { AvisoFallo } from './aviso-fallo';
import type { FalloPago, PasoPago } from './use-pago-pedido';

type Props = {
  lang: Locale;
  dict: Dictionary;
  sedeSlug: string;
  paquete: PaqueteCatalogo;
  motor: 'reserva' | 'orden';
  moneda: Moneda;
  pagos: PasoPago[];
  fallo: FalloPago | null;
  falloEnVivo: boolean;
  fallos: number;
  nombreEmpresa: (slug: string) => string;
  /** Stepper ya resuelto por la vista: el del cobro que falló, o el de 4 pasos. */
  stepper: ComponentProps<typeof PaginaCheckout>['stepper'];
  /** Cruza-empresa con el fallo en vivo: reintenta con otra tarjeta, sin volver al formulario. */
  onReintentarDirecto: () => void | Promise<unknown>;
  /** Vuelve al formulario con checkout_id y Turnstile nuevos. */
  onReiniciar: () => void;
};

/**
 * Pantalla de fallo del paquete: qué empresa rechazó, el motivo del banco, el
 * aviso de retención del pago anterior y el botón de reintento (o de elegir otra fecha).
 */
export function PantallaFallo({
  lang, dict, sedeSlug, paquete, motor, moneda, pagos, fallo, falloEnVivo, fallos, nombreEmpresa,
  stepper, onReintentarDirecto, onReiniciar,
}: Props) {
  const { checkout, pedido: textos, nav, footer } = dict;
  const textosFallo = textos.fail;
  const detalle = fallo;
  const rechazo = detalle !== null && detalle.codigo !== 'captura' && detalle.empresaSlug !== null;
  const retenidas = rechazo ? pagosRetenidosAntes(pagos, detalle.indice) : [];
  const reintentoDirecto = motor === 'orden' && falloEnVivo;
  const titulo = detalle?.empresaSlug
    ? (rechazo ? textosFallo.rechazoEmpresa : textosFallo.capturaEmpresa).replace('{empresa}', nombreEmpresa(detalle.empresaSlug))
    : textosFallo.title;
  const lineasDinero = rechazo
    ? [
      retenidas.length > 0
        ? `${textosFallo.sinCobro} ${textosFallo.liberaRetencion.replace('{empresas}', retenidas.map((r) => nombreEmpresa(r.empresaSlug)).join(', '))}`
        : textosFallo.sinCobro,
      ...(retenidas.length > 0 ? [textosFallo.dobleRetencion.replace('{monto}',
        formatearPrecio(retenidas.reduce((suma, r) => suma + Number(r.monto), 0), moneda))] : []),
    ]
    : [detalle ? textosFallo.liberaGeneral : textosFallo.body];
  // Motor reserva: el webhook cancelo y reembolso porque el lugar se fue. No hubo rechazo de tarjeta.
  const lugarNoAsegurado = motor === 'reserva';
  const ayuda = ofreceAyuda(fallos) && tieneWhatsapp
    ? { etiqueta: textosFallo.ayuda, href: whatsappHref(textosFallo.ayudaMensaje.replace('{paquete}', paquete.nombre)) }
    : null;

  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} minimo />
      <div aria-hidden className="h-[calc(1.5rem_+_var(--nav-alto))]" />
      <CheckoutStepper stepper={checkout.stepper} {...stepper} />
      <div className="mx-auto max-w-xl px-6 pt-8 pb-20 sm:px-8">
        <AvisoFallo
          titulo={lugarNoAsegurado ? checkout.lugarNoAseguradoTitulo : titulo}
          motivo={rechazo ? textosFallo.motivos[claveMotivoRechazo(detalle.codigo)] : null}
          lineasDinero={lugarNoAsegurado ? [checkout.lugarNoAseguradoCuerpo] : lineasDinero}
          etiquetaBoton={lugarNoAsegurado
            ? checkout.eligeOtraFecha
            : reintentoDirecto ? textosFallo.retryOtraTarjeta : textosFallo.retry}
          onReintentar={reintentoDirecto ? () => void onReintentarDirecto() : onReiniciar}
          ayuda={ayuda}
        />
      </div>
      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );
}
