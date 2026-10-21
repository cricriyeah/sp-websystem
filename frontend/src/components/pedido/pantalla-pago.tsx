import type { ComponentProps } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { ItemPaso } from '@/components/checkout/item-paso';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { FormularioPagoDiferido } from '@/components/checkout/pago/pago-diferido';
import { AsistenteMovil } from '@/components/reserva/asistente-movil';
import { useMovil } from '@/components/reserva/use-movil';
import { StripePanel } from '@/components/stripe-panel';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { fechaDeComponente } from '@/lib/calendario-paquete';
import type { ComponentePedido } from '@/lib/pedido-payload';
import { numeroDePaso, rotuloDePaso } from '@/lib/pasos-checkout';
import { formatearPrecio } from '@/lib/pricing-paquete';
import type { CargoVisible, EstadoCargo } from '@/components/checkout/pago/renglon-cargo';
import { EncabezadoPago } from './encabezado-pago';
import { ReservaPlegable } from './reserva-plegable';
import { useCancelarOrden } from './use-cancelar-orden';
import type { usePagoPedido } from './use-pago-pedido';

type Linea = { etiqueta: string; valor: string };
type Stepper = ComponentProps<typeof PaginaCheckout>['stepper'];

type Props = {
  lang: Locale;
  dict: Dictionary;
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
  volverHref: string;
  empresa?: { nombre: string; logo?: string };
  sellos?: { nombre: string; logo?: string }[];
  totalMovil: string | undefined;
  total: string;
  totalConMoneda: string | null;
  ayudaMensaje: string;
  detalleCompra: string;
  lineasViaje: Linea[];
  lineasContacto: Linea[];
  componentes: Record<string, ComponentePedido>;
  /** Fecha de inicio elegida (o la mínima): de ella salen las fechas de cada servicio. */
  inicio: string;
  formatearFecha: (iso: string) => string;
  lineaPunto: (traslado: ComponentePedido['traslado']) => Linea[];
  /** Nodo donde el panel pinta "Cómo pagas" (el mismo estado de la vista). */
  destinoTarjetaPago: HTMLElement | null;
  setDestinoTarjetaPago: (nodo: HTMLElement | null) => void;
  sedeSlug: string;
  /** `{ nombre, logo }` por slug (de `content/empresas`): el logo de cada cargo. */
  empresas: Record<string, { nombre: string; logo?: string }>;
  /** La orden se canceló y se liberó lo retenido: vuelve al formulario con este aviso. */
  onOrdenCancelada: (linea: string) => void;
};

/**
 * Paso de pago del paquete (fase `pagando`): respuestas ya dadas en un
 * plegable, "Cómo pagas" ya con el pago creado, la franja de cobros y el
 * formulario de tarjeta, y a la derecha el resumen. Sin estado propio: el
 * estado de cobro vive en `usePagoPedido` y en la vista; el formulario de
 * tarjeta y el panel se remontan por empresa (`key`), como siempre.
 */
export function PantallaPago({
  lang, dict, paquete, motor, moneda, pago, cantidadCargos, nombreEmpresa, personasPaquete,
  stepperPagos, volverHref, empresa, sellos, totalMovil, totalConMoneda, ayudaMensaje, detalleCompra, lineasViaje,
  lineasContacto, componentes, inicio, formatearFecha, lineaPunto, destinoTarjetaPago, setDestinoTarjetaPago,
  sedeSlug, empresas, onOrdenCancelada,
}: Props) {
  const { checkout, feedback, pedido: textos } = dict;
  const movil = useMovil();
  // Cruza-empresa con la orden creada: la flecha y Atrás piden confirmar antes de cancelarla.
  const cancelacion = useCancelarOrden({
    dict,
    activo: motor === 'orden' && pago.ordenId !== null,
    sedeSlug,
    ordenId: pago.ordenId,
    checkoutId: pago.checkoutId,
    producto: paquete.nombre,
    onLiberada: onOrdenCancelada,
  });
  const pasoPago = pago.pagos[pago.indice];
  if (!pasoPago) return null;
  const n = cantidadCargos || pago.pagos.length;
  const monto = formatearPrecio(Number(pasoPago.monto), moneda);
  const totalPago = formatearPrecio(Number(pasoPago.precioTotal ?? pasoPago.monto), moneda);
  const etiqueta = nombreEmpresa(pasoPago.empresaSlug);
  // Un renglón por cobro: los anteriores quedan retenidos hasta el último; ninguno se cobra antes.
  const cargos: CargoVisible[] = pago.pagos.map((item, indice) => {
    const estado: EstadoCargo = indice < pago.indice ? 'retenido' : 'pendiente';
    return {
      empresa: nombreEmpresa(item.empresaSlug),
      logo: empresas[item.empresaSlug]?.logo,
      servicio: paquete.servicios_asociados
        .filter((c) => c.servicio.empresa_slug === item.empresaSlug)
        .map((c) => c.servicio.nombre).join(', '),
      monto: `${formatearPrecio(Number(item.monto), moneda)} ${moneda}`,
      estado,
      etiquetaEstado: textos.estadoCargo[estado],
      actual: indice === pago.indice,
    };
  });
  const etiquetaBotonPago = n === 1
    ? paquete.precio_depende_de_personas
      ? (personasPaquete === 1 ? textos.payOne : textos.payPeople.replace('{n}', String(personasPaquete)))
        .replace('{amount}', `${monto} ${moneda}`)
      : textos.payButtonSingle.replace('{amount}', monto)
    : textos.payButton.replace('{amount}', monto).replace('{empresa}', etiqueta)
      .replace('{n}', String(pago.indice + 1)).replace('{total}', String(n));

  // Cruza-empresa: la secuencia de pagos vive en un solo componente que se remonta por empresa.
  const formulario = (
    <FormularioPagoDiferido
      lang={lang}
      key={pasoPago.empresaSlug}
      checkout={checkout}
      feedback={feedback}
      ayudaMensaje={ayudaMensaje}
      pago={{ client_secret: pasoPago.clientSecret, publishable_key: pasoPago.publishableKey }}
      venceEn={pasoPago.venceEn}
      encabezadoPago={<EncabezadoPago dict={dict} cargos={cargos} indice={pago.indice} total={totalConMoneda ?? undefined} />}
      etiquetaBotonPago={etiquetaBotonPago}
      apartadoHasta={pago.apartadoHasta}
      antesDePagar={motor === 'reserva' ? pago.antesDePagar : undefined}
      onPagoConfirmado={pago.onPagoConfirmado}
      onPagoRechazado={pago.onPagoRechazado}
    />
  );
  // Móvil: una pantalla por cobro. La primera línea dice cuál es, a quién y cuánto.
  const pantallaMovil = (
    <AsistenteMovil
      id={`tarjeta-${pago.indice}`}
      titulo={checkout.barra.tarjeta}
      antetitulo={n > 1
        ? `${textos.payStep.replace('{n}', String(pago.indice + 1)).replace('{total}', String(n))} · ${etiqueta} · ${monto} ${moneda}`
        : undefined}
      soloFundido
      anuncio={`${rotuloDePaso(checkout.stepper.stepOf, 'pago')}: ${checkout.stepper.pago}`}
      accion={{ etiqueta: etiquetaBotonPago, alPulsar: () => {}, deshabilitado: true, razon: checkout.barra.cargandoPago }}
    >
      {formulario}
    </AsistenteMovil>
  );

  return (
    <>
    <PaginaCheckout
      lang={lang}
      dict={dict}
      volverHref={volverHref}
      alPasoAnterior={motor === 'orden' && !cancelacion.cerrada ? cancelacion.abrir : undefined}
      aviso={cancelacion.aviso ?? undefined}
      empresa={empresa}
      empresasDeslinde={[...new Set(paquete.servicios_asociados.map((c) => c.servicio.empresa_slug))]}
      marcaFija={motor === 'orden'}
      volverLabel={textos.back}
      encabezado={
        <EncabezadoCompra
          titulo={checkout.tituloPagina}
            detalle={[paquete.nombre, detalleCompra].filter(Boolean).join(' · ')}
        />
      }
      stepper={stepperPagos(pago.indice, Number(pasoPago.monto)) ?? (Number(pasoPago.monto) < Number(pasoPago.precioTotal ?? pasoPago.monto)
        // Un solo cobro con anticipo: la cifra del paso es el anticipo, no el total.
        ? { actual: numeroDePaso('pago'), totalMovil: `${monto} ${moneda}`, rotulo: checkout.stepper.payNow, totalGeneral: `${totalPago} ${moneda}` }
        : { actual: numeroDePaso('pago'), totalMovil })}
      pasos={cancelacion.cerrada ? null : movil ? pantallaMovil : (
        <>
          {/* Retomada desde el servidor: sin Viaje ni Datos inventados; solo el pago y su resumen. */}
          {!pago.retomado && (
          <ReservaPlegable
            titulo={textos.yourBooking}
            etiquetaEstado={textos.bookingSaved}
            notaBloqueada={textos.lockedNote}
            ctaAyuda={textos.lockedCta}
            mensajeAyuda={ayudaMensaje}
          >
          <ItemPaso>
            <CheckoutSectionCard
              title={checkout.tripHeadline}
              estado="completado"
              detalle={lineasViaje}
            >
              {null}
            </CheckoutSectionCard>
          </ItemPaso>
          <ItemPaso unida>
            <CheckoutSectionCard
              title={checkout.contactHeadline}
              estado="completado"
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
          )}

          {/* "Cómo pagas" (ya con el pago creado, un renglón) se pinta aquí. */}
          <div ref={setDestinoTarjetaPago} />

          {/* El pago es el cuarto paso: su tarjeta va justo debajo de las
              respuestas ya dadas. En cruza-empresa se remonta por empresa
              (cada una cobra con su propia clave y secreto). */}
          {formulario}
        </>
      )}
      pedido={
        <StripePanel
          key={pasoPago.empresaSlug}
          lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
          waiverAccepted={true} onWaiverChange={() => {}} errorWaiver={false}
          lines={[{ label: etiqueta, amount: totalPago }]} lineasViaje={pago.retomado ? [] : lineasViaje} sellos={sellos}
          cargos={cargos.length > 1 ? cargos : undefined}
          notaCargos={cargos.length > 1 ? textos.chargesSum.replace('{total}', totalConMoneda ?? '') : undefined}
          destinoTarjeta={destinoTarjetaPago}
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
    {cancelacion.dialogo}
    </>
  );
}
