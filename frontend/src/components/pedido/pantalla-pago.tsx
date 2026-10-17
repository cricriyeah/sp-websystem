import type { ComponentProps } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { ItemPaso } from '@/components/checkout/item-paso';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { FormularioPagoDiferido } from '@/components/checkout/pago/pago-diferido';
import { StripePanel } from '@/components/stripe-panel';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { fechaDeComponente } from '@/lib/calendario-paquete';
import type { ComponentePedido } from '@/lib/pedido-payload';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { EncabezadoPago } from './encabezado-pago';
import { FranjaResumen } from './franja-resumen';
import { ReservaPlegable } from './reserva-plegable';
import type { usePagoPedido } from './use-pago-pedido';

type Linea = { etiqueta: string; valor: string };
type Stepper = ComponentProps<typeof PaginaCheckout>['stepper'];

type Props = {
  lang: Locale;
  dict: Dictionary;
  sedeSlug: string;
  paquete: PaqueteCatalogo;
  motor: 'reserva' | 'orden';
  moneda: Moneda;
  /** El hook del pago, entero: este paso lee el cobro en curso y le pasa sus callbacks a la tarjeta. */
  pago: ReturnType<typeof usePagoPedido>;
  cantidadCargos: number;
  nombreEmpresa: (slug: string) => string;
  personasPaquete: number;
  /** Stepper de la vista con un cobro por paso (null si hay un solo cobro). */
  stepperPagos: (indicePago: number, monto?: number) => Stepper | null;
  totalMovil: string | undefined;
  total: string;
  totalConMoneda: string | null;
  ayudaMensaje: string;
  detalleCompra: string;
  resumenViaje: string;
  lineasViaje: Linea[];
  lineasContacto: Linea[];
  contacto: { fullName: string; email: string };
  componentes: Record<string, ComponentePedido>;
  /** Fecha de inicio elegida (o la mínima): de ella salen las fechas de cada servicio. */
  inicio: string;
  formatearFecha: (iso: string) => string;
  lineaPunto: (traslado: ComponentePedido['traslado']) => Linea[];
  /** Nodo donde el panel pinta "Cómo pagas" (el mismo estado de la vista). */
  destinoTarjetaPago: HTMLElement | null;
  setDestinoTarjetaPago: (nodo: HTMLElement | null) => void;
};

/**
 * Paso de pago del paquete (fase `pagando`): respuestas ya dadas en un
 * plegable, "Cómo pagas" ya con el pago creado, la franja de cobros y el
 * formulario de tarjeta, y a la derecha el resumen. Sin estado propio: el
 * estado de cobro vive en `usePagoPedido` y en la vista; el formulario de
 * tarjeta y el panel se remontan por empresa (`key`), como siempre.
 */
export function PantallaPago({
  lang, dict, sedeSlug, paquete, motor, moneda, pago, cantidadCargos, nombreEmpresa, personasPaquete,
  stepperPagos, totalMovil, total, totalConMoneda, ayudaMensaje, detalleCompra, resumenViaje, lineasViaje,
  lineasContacto, contacto, componentes, inicio, formatearFecha, lineaPunto, destinoTarjetaPago, setDestinoTarjetaPago,
}: Props) {
  const { checkout, feedback, pedido: textos } = dict;
  const pasoPago = pago.pagos[pago.indice];
  if (!pasoPago) return null;
  const n = cantidadCargos || pago.pagos.length;
  const monto = formatearPrecio(Number(pasoPago.monto), moneda);
  const totalPago = formatearPrecio(Number(pasoPago.precioTotal ?? pasoPago.monto), moneda);
  const etiqueta = nombreEmpresa(pasoPago.empresaSlug);
  const pasosPago = pago.pagos.map((item, indice) => ({
    etiqueta: nombreEmpresa(item.empresaSlug),
    monto: formatearPrecio(Number(item.monto), moneda),
    estado: (indice < pago.indice ? 'hecho' : indice === pago.indice ? 'actual' : 'pendiente') as 'hecho' | 'actual' | 'pendiente',
  }));
  // Lo que queda por cobrar después de este pago: los pagos que faltan y, con
  // anticipo, el saldo de la empresa actual.
  const faltaPorCobrar = pago.pagos.slice(pago.indice + 1).reduce((suma, p) => suma + Number(p.monto), 0)
    + Math.max(0, Number(pasoPago.precioTotal ?? pasoPago.monto) - Number(pasoPago.monto));
  const etiquetaBotonPago = n === 1
    ? paquete.precio_depende_de_personas
      ? (personasPaquete === 1 ? textos.payOne : textos.payPeople.replace('{n}', String(personasPaquete)))
        .replace('{amount}', `${monto} ${moneda}`)
      : textos.payButtonSingle.replace('{amount}', monto)
    : textos.payButton.replace('{amount}', monto).replace('{empresa}', etiqueta)
      .replace('{n}', String(pago.indice + 1)).replace('{total}', String(n));

  return (
    <PaginaCheckout
      lang={lang}
      dict={dict}
      sedeSlug={sedeSlug}
      volverHref={`/${lang}/sede/${sedeSlug}`}
      volverLabel={textos.back}
      encabezado={
        <EncabezadoCompra
          kicker={checkout.purchaseKicker}
          nombre={paquete.nombre}
          detalle={detalleCompra}
        />
      }
      stepper={stepperPagos(pago.indice, Number(pasoPago.monto)) ?? (Number(pasoPago.monto) < Number(pasoPago.precioTotal ?? pasoPago.monto)
        // Un solo cobro con anticipo: la cifra del paso es el anticipo, no el total.
        ? { actual: 4, totalMovil: `${monto} ${moneda}`, rotulo: checkout.stepper.payNow, totalGeneral: `${totalPago} ${moneda}` }
        : { actual: 4, totalMovil })}
      pasos={
        <>
          <ReservaPlegable
            titulo={textos.yourBooking}
            etiquetaEstado={textos.bookingSaved}
            resumen={resumenViaje || paquete.nombre}
            notaBloqueada={textos.lockedNote}
            ctaAyuda={textos.lockedCta}
            mensajeAyuda={ayudaMensaje}
          >
          <ItemPaso>
            <CheckoutSectionCard
              title={checkout.tripHeadline}
              estado="completado"
              resumen={resumenViaje}
              detalle={lineasViaje}
            >
              {null}
            </CheckoutSectionCard>
          </ItemPaso>
          <ItemPaso unida>
            <CheckoutSectionCard
              title={checkout.contactHeadline}
              estado="completado"
              resumen={`${contacto.fullName} · ${contacto.email}`}
              detalle={lineasContacto}
            >
              {null}
            </CheckoutSectionCard>
          </ItemPaso>
          {paquete.servicios_asociados.map((item) => {
            const componente = componentes[item.servicio.slug];
            const personas = componente?.personas ?? item.personas_incluidas;
            return (
              <ItemPaso key={item.id} unida>
                <CheckoutSectionCard
                  title={item.servicio.nombre}
                  etiqueta={cantidadCargos > 1 ? nombreEmpresa(item.servicio.empresa_slug) : undefined}
                  estado="completado"
                  resumen={`${personas} ${personas === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`}
                  detalle={[
                    { etiqueta: checkout.summary.date, valor: formatearFecha(fechaDeComponente(inicio, item.dia_estancia)) },
                    { etiqueta: checkout.summary.people, valor: String(personas) },
                    ...lineaPunto(componente?.traslado),
                  ]}
                >
                  {null}
                </CheckoutSectionCard>
              </ItemPaso>
            );
          })}
          </ReservaPlegable>

          {/* "Cómo pagas" (ya con el pago creado, un renglón) se pinta aquí. */}
          <div ref={setDestinoTarjetaPago} />

          {/* El pago es el cuarto paso: su tarjeta va justo debajo de las
              respuestas ya dadas. En cruza-empresa se remonta por empresa
              (cada una cobra con su propia clave y secreto). */}
          <FranjaResumen
            dict={dict}
            total={total}
            pagos={pasosPago}
            saldo={pasosPago.length === 1 && faltaPorCobrar > 0 ? formatearPrecio(faltaPorCobrar, moneda) : null}
          />
          <FormularioPagoDiferido
            lang={lang}
            key={pasoPago.empresaSlug}
            checkout={checkout}
            feedback={feedback}
            ayudaMensaje={ayudaMensaje}
            pago={{ client_secret: pasoPago.clientSecret, publishable_key: pasoPago.publishableKey }}
            venceEn={pasoPago.venceEn}
            encabezadoPago={<EncabezadoPago dict={dict} pasos={pasosPago} indice={pago.indice} total={totalConMoneda ?? undefined} />}
            etiquetaBotonPago={etiquetaBotonPago}
            apartadoHasta={pago.apartadoHasta}
            antesDePagar={motor === 'reserva' ? pago.antesDePagar : undefined}
            onPagoConfirmado={pago.onPagoConfirmado}
            onPagoRechazado={pago.onPagoRechazado}
          />
        </>
      }
      pedido={
        <StripePanel
          key={pasoPago.empresaSlug}
          lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
          waiverAccepted={true} onWaiverChange={() => {}} errorWaiver={false}
          lines={[{ label: etiqueta, amount: totalPago }]} lineasViaje={lineasViaje}
          destinoTarjeta={destinoTarjetaPago} resumenSoloEscritorio
          total={totalPago} amountDueNow={monto}
          moneda={moneda} onMonedaChange={() => {}} usdDisponible={false}
          formaPago="completo" onFormaPagoChange={() => {}} formaPagoDisponible={false}
          codigoPromocional="" onCodigoPromocionalChange={() => {}}
          codigoPromocionalDisponible={false} promoEstado="idle" promoPorcentaje={null}
          phase="payment" error=""
          onSubmit={() => {}} onCaptchaToken={() => {}}
        />
      }
    />
  );
}
