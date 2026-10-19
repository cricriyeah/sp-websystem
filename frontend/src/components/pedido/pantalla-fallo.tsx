import type { ComponentProps } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { LineaProgreso } from '@/components/reserva/linea-progreso';
import type { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { CabeceraMinima } from '@/components/reserva/cabecera-minima';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { claveMotivoRechazo, ofreceAyuda, pagosRetenidosAntes } from '@/lib/fallo-pago';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { AvisoAccion } from '@/components/ui/aviso-accion';
import { problemaDe } from '@/lib/problema-reserva';
import { WhatsappLogo } from '@phosphor-icons/react';
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

  // El lugar no asegurado es un «sin cupo» con reembolso; lo demás es un rechazo de tarjeta.
  const motivoBanco = rechazo ? textosFallo.motivos[claveMotivoRechazo(detalle.codigo)] : null;
  const problema = lugarNoAsegurado
    ? problemaDe('sin_cupo', { lineasDinero: [checkout.lugarNoAseguradoCuerpo], tieneWhatsapp }, {
      ...checkout.problema,
      sin_cupo: { ...checkout.problema.sin_cupo, titulo: checkout.lugarNoAseguradoTitulo, cuerpo: '' },
    })
    : problemaDe('tarjeta_rechazada', {
      lineasDinero: [...(motivoBanco ? [motivoBanco] : []), ...lineasDinero], tieneWhatsapp,
    }, {
      ...checkout.problema,
      tarjeta_rechazada: {
        ...checkout.problema.tarjeta_rechazada,
        titulo,
        cuerpo: '',
        accion: reintentoDirecto ? textosFallo.retryOtraTarjeta : textosFallo.retry,
      },
    });

  return (
    <div className="min-h-dvh bg-background">
      <CabeceraMinima lang={lang} nav={nav} volverHref={`/${lang}/sede/${sedeSlug}`} volverLabel={checkout.back} marcaFija />
      <div aria-hidden className="h-[calc(1.5rem_+_var(--nav-alto))]" />
      <LineaProgreso
        className="mx-auto mt-4 max-w-xl px-6 sm:px-8"
        actual={stepper.actual}
        nombres={[checkout.stepper.viaje, checkout.stepper.datos, checkout.stepper.pago]}
        plantilla={checkout.stepper.stepOf}
      />
      <div className="mx-auto max-w-xl px-6 pt-8 pb-20 sm:px-8">
        <AvisoAccion
          problema={problema}
          alAccionar={(clave) => {
            if (clave === 'otra_tarjeta' && reintentoDirecto) void onReintentarDirecto();
            else onReiniciar();
          }}
        />
        {ayuda && (
          <a href={ayuda.href} target="_blank" rel="noopener"
            className="mt-3 flex min-h-11 items-center justify-center gap-2 texto-pequeno font-semibold text-tinta-suave hover:text-foreground">
            <WhatsappLogo size={18} weight="fill" />
            {ayuda.etiqueta}
          </a>
        )}
      </div>
      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );
}
