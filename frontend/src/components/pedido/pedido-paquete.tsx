'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { EnvelopeSimple, Phone, User } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CheckoutStepper } from '@/components/checkout-stepper';
import { ErrorBlock } from '@/components/error-block';
import { FieldError } from '@/components/field-error';
import { SiteHeader } from '@/components/site-header';
import { StripePanel } from '@/components/stripe-panel';
import { TimeField } from '@/components/time-field';
import { validarCodigoPromocional, type PaqueteCatalogo, type PuntoEncuentro, type TrasladosCatalogo } from '@/lib/api';
import { fechaDeComponente, fechaSalida, nochesDelPaquete } from '@/lib/calendario-paquete';
import { fromLocalISODate } from '@/lib/dates';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { mensajeDeAyuda, mensajeDeError } from '@/lib/errores';
import { claveMotivoRechazo, ofreceAyuda, pagosRetenidosAntes } from '@/lib/fallo-pago';
import { intlLocale } from '@/lib/intl';
import { calcularPedido, montoInicial, usdDisponible } from '@/lib/pedido-paquete';
import { armarPayloadOrden, armarPayloadReserva, zonaEfectivaDeTraslado } from '@/lib/pedido-payload';
import { erroresPersonalizaciones } from '@/lib/personalizaciones';
import { leerRef } from '@/lib/ref';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { AvisoCargos } from './aviso-cargos';
import { AvisoFallo } from './aviso-fallo';
import { EncabezadoPago } from './encabezado-pago';
import { GrupoServicio } from './grupo-servicio';
import { usePagoPedido } from './use-pago-pedido';
import { usePedidoEstado } from './use-pedido-estado';

type Props = {
  lang: Locale;
  dict: Dictionary;
  paquete: PaqueteCatalogo;
  sedeSlug: string;
  tarifasPorEmpresa: Record<string, TrasladosCatalogo['tarifas']>;
  puntosPorEmpresa: Record<string, PuntoEncuentro[]>;
  minDate: string;
};

export function PedidoPaquete({ lang, dict, paquete, sedeSlug, tarifasPorEmpresa, puntosPorEmpresa, minDate }: Props) {
  const { checkout, booking, feedback, pedido: textos, nav, footer, traslados } = dict;
  const motor = paquete.es_cruza_empresa ? 'orden' : 'reserva';
  const [estado, despachar] = usePedidoEstado(paquete, {
    moneda: 'MXN',
    puntoInicial: (empresa) => puntosPorEmpresa[empresa]?.[0]?.id ?? null,
  });
  const captcha = useRef('');
  const [paso, setPaso] = useState(1);
  const [datosEditando, setDatosEditando] = useState(false);
  const [gruposCompletados, setGruposCompletados] = useState(0);
  const [grupoEditando, setGrupoEditando] = useState<number | null>(null);
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [errorWaiver, setErrorWaiver] = useState(false);
  const [erroresContacto, setErroresContacto] = useState<Partial<Record<'fullName' | 'phone' | 'email', string>>>({});
  const [errorDetalles, setErrorDetalles] = useState('');
  const [codigoPromocional, setCodigoPromocional] = useState('');
  const [promoEstado, setPromoEstado] = useState<'idle' | 'verificando' | 'valido' | 'invalido'>('idle');
  const [promoPorcentaje, setPromoPorcentaje] = useState<string | null>(null);

  const componentes = useMemo(
    () => paquete.servicios_asociados.map((c) => ({ dia_estancia: c.dia_estancia, estrategia_cupo: c.servicio.estrategia_cupo, noches: c.noches })),
    [paquete],
  );
  const salida = estado.inicio ? fechaSalida(estado.inicio, componentes) : null;
  const noches = nochesDelPaquete(componentes);

  // Misma regla que el backend (DetalleTransporte.zona_efectiva): solo redondo_actividad usa zona.
  const zonaDePunto = (id: number | null) => Object.values(puntosPorEmpresa).flat().find((p) => p.id === id)?.zona ?? '';
  const selecciones = useMemo(
    () => Object.fromEntries(Object.entries(estado.componentes).map(([slug, c]) => [slug, {
      personas: c.personas, extras: c.extras,
      traslado: c.traslado ? { tipo: c.traslado.tipo, zona: zonaEfectivaDeTraslado(c.traslado, zonaDePunto) } : undefined,
    }])),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- zonaDePunto solo depende de puntosPorEmpresa
    [estado.componentes, puntosPorEmpresa],
  );
  const pedido = calcularPedido(paquete, selecciones, estado.moneda, tarifasPorEmpresa);
  const conUsd = usdDisponible(paquete, tarifasPorEmpresa);
  const cargos = pedido?.cargos ?? [];
  const cantidadCargos = cargos.length;
  const nombreEmpresa = (slug: string) => slug === paquete.empresa_lider_slug
    ? paquete.empresa_lider
    : slug.split('-').map((parte) => parte.charAt(0).toUpperCase() + parte.slice(1)).join(' ');
  const formatearFecha = (iso: string) => new Intl.DateTimeFormat(intlLocale(lang), {
    day: 'numeric', month: 'long', year: 'numeric',
  }).format(fromLocalISODate(iso));
  const descuento = pedido && motor === 'reserva' && promoEstado === 'valido' && promoPorcentaje
    ? Math.min(pedido.total, Math.round(pedido.total * Number(promoPorcentaje) / 100 * 100) / 100)
    : 0;
  const totalConDescuento = pedido ? pedido.total - descuento : null;
  const total = formatearPrecio(totalConDescuento, estado.moneda);
  const ahora = totalConDescuento !== null ? formatearPrecio(
    paquete.permite_anticipo
      ? montoInicial(totalConDescuento, estado.formaPago, paquete.porcentaje_anticipo)
      : totalConDescuento,
    estado.moneda,
  ) : '—';
  const ayudaMensaje = mensajeDeAyuda(feedback.helpMessage, {
    fecha: estado.inicio ?? minDate,
    hora: estado.hora,
    personas: paquete.servicios_asociados[0] ? estado.componentes[paquete.servicios_asociados[0].servicio.slug]?.personas ?? 1 : 1,
  });

  const pago = usePagoPedido({
    motor,
    sedeSlug,
    empresaSlug: paquete.empresa_lider_slug,
    paqueteSlug: paquete.slug,
    formaPago: estado.formaPago,
    codigoPromocional: motor === 'reserva' ? codigoPromocional : undefined,
    captchaToken: () => captcha.current,
    mensajeDeError: (err) => mensajeDeError(err, checkout, feedback),
    armarPayload: (checkoutId) => {
      const args = {
        checkoutId, paquete, componentes: estado.componentes, inicio: estado.inicio ?? minDate,
        hora: estado.hora, moneda: estado.moneda, contacto: estado.contacto, ref: leerRef(),
        zonaDePunto,
      };
      return motor === 'orden' ? armarPayloadOrden(args) : armarPayloadReserva(args);
    },
  });

  useEffect(() => {
    if (motor !== 'reserva' || !codigoPromocional.trim() || !estado.contacto.email.trim()) return;
    let activo = true;
    const timer = setTimeout(() => {
      validarCodigoPromocional(codigoPromocional.trim(), estado.contacto.email.trim(), paquete.empresa_lider_slug)
        .then((resultado) => {
          if (!activo) return;
          setPromoEstado(resultado.valido ? 'valido' : 'invalido');
          setPromoPorcentaje(resultado.porcentaje_descuento);
        })
        .catch(() => {
          if (activo) setPromoEstado('idle');
        });
    }, 400);
    return () => { activo = false; clearTimeout(timer); };
  }, [motor, codigoPromocional, estado.contacto.email, paquete.empresa_lider_slug]);

  const validarDatos = () => {
    const errores: typeof erroresContacto = {};
    const nombre = estado.contacto.fullName.trim();
    const telefono = estado.contacto.phone.trim();
    const correo = estado.contacto.email.trim();
    if (!nombre) errores.fullName = checkout.missingFields;
    else if (/\d/.test(nombre) || !/\p{L}/u.test(nombre)) errores.fullName = checkout.invalidName;
    if (!telefono) errores.phone = checkout.missingFields;
    else if (!/^[\d\s+()\-.]+$/.test(telefono) || !/^\d{10,15}$/.test(telefono.replace(/\D/g, ''))) {
      errores.phone = checkout.invalidPhone;
    }
    if (!correo) errores.email = checkout.missingFields;
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo)) errores.email = checkout.invalidEmail;
    setErroresContacto(errores);
    return Object.keys(errores).length === 0;
  };

  const confirmarDatos = () => {
    if (!validarDatos()) return;
    setDatosEditando(false);
    setPaso((actual) => Math.max(actual, 2));
  };

  const errorDeGrupo = (indice: number): string => {
    if (!estado.inicio) return traslados.errors.seleccionaFecha;
    const item = paquete.servicios_asociados[indice];
    const actual = estado.componentes[item.servicio.slug];
    const errores = erroresPersonalizaciones(item.servicio.personalizaciones, actual.extras);
    const primerError = Object.values(errores)[0];
    if (primerError) return checkout.personalizacionErrors[primerError];
    const t = actual.traslado;
    if (t) {
      if (t.modo === 'catalogo' && t.puntoEncuentroId === null) {
        return traslados.errors.seleccionaHospedaje;
      }
      if (t.modo === 'personalizada' && !t.direccion.trim()) {
        return traslados.errors.seleccionaHospedaje;
      }
      if (t.tipo === 'redondo_actividad' && !zonaEfectivaDeTraslado(t, zonaDePunto)) {
        return traslados.errors.seleccionaZona;
      }
      if (t.tipo === 'redondo_aeropuerto' && noches === null) {
        if (!t.fechaRegreso) return traslados.errors.seleccionaFechaRegreso;
        if (t.fechaRegreso <= fechaDeComponente(estado.inicio, item.dia_estancia)) {
          return traslados.errors.seleccionaFechaRegreso;
        }
      }
    }
    return '';
  };

  const confirmarGrupo = (indice: number) => {
    const error = errorDeGrupo(indice);
    if (error) return setErrorDetalles(error);
    setErrorDetalles('');
    setGruposCompletados(indice + 1);
    if (indice === paquete.servicios_asociados.length - 1) setPaso(3);
  };

  const enviar = () => {
    if (!validarDatos()) {
      setDatosEditando(true);
      return;
    }
    for (let indice = 0; indice < paquete.servicios_asociados.length; indice++) {
      const error = errorDeGrupo(indice);
      if (error) {
        setErrorDetalles(error);
        setGrupoEditando(indice);
        return;
      }
    }
    if (!waiverAccepted) return setErrorWaiver(true);
    if (!pedido) return setErrorDetalles(feedback.error.no_disponible);
    setErrorDetalles('');
    void pago.enviar();
  };

  const pasos = [checkout.stepper.contact, checkout.stepper.extras, checkout.confirmStep, checkout.stepper.payment];

  if (pago.fase === 'exito') return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{textos.success.title}</h1>
        <p className="text-sm text-muted">{textos.success.body}</p>
        <div className="w-full rounded-xl border border-border bg-card p-5 text-left">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            {textos.success.componentsHeadline}
          </p>
          <ul className="flex flex-col gap-2">
            {paquete.servicios_asociados.map((item) => (
              <li key={item.id} className="flex flex-wrap justify-between gap-2 text-sm text-foreground">
                <span>{item.servicio.nombre}</span>
                <span className="text-muted">
                  {formatearFecha(fechaDeComponente(estado.inicio ?? minDate, item.dia_estancia))}
                  {' · '}{estado.componentes[item.servicio.slug]?.personas ?? item.personas_incluidas} {checkout.peopleLabel.toLowerCase()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );

  // Tras un fallo en esta misma sesión el formulario sigue en memoria: se reintenta con una
  // orden nueva directo al pago. Tras una recarga no hay datos que conservar: se vuelve al formulario.
  const reintentar = async () => {
    const llegoAlPago = await pago.reintentar();
    if (!llegoAlPago) setGrupoEditando(0); // p. ej. ya no hay cupo: se abre la fecha para cambiarla
  };

  if (pago.fase === 'fallo') {
    const textosFallo = textos.fail;
    const detalle = pago.fallo;
    const rechazo = detalle !== null && detalle.codigo !== 'captura' && detalle.empresaSlug !== null;
    const retenidas = rechazo ? pagosRetenidosAntes(pago.pagos, detalle.indice) : [];
    const reintentoDirecto = motor === 'orden' && pago.falloEnVivo;
    const titulo = detalle?.empresaSlug
      ? (rechazo ? textosFallo.rechazoEmpresa : textosFallo.capturaEmpresa).replace('{empresa}', nombreEmpresa(detalle.empresaSlug))
      : textosFallo.title;
    const lineasDinero = rechazo
      ? [
        retenidas.length > 0
          ? `${textosFallo.sinCobro} ${textosFallo.liberaRetencion.replace('{empresas}', retenidas.map((r) => nombreEmpresa(r.empresaSlug)).join(', '))}`
          : textosFallo.sinCobro,
        ...(retenidas.length > 0 ? [textosFallo.dobleRetencion.replace('{monto}',
          formatearPrecio(retenidas.reduce((suma, r) => suma + Number(r.monto), 0), estado.moneda))] : []),
      ]
      : [detalle ? textosFallo.liberaGeneral : textosFallo.body];
    const ayuda = ofreceAyuda(pago.fallos) && tieneWhatsapp
      ? { etiqueta: textosFallo.ayuda, href: whatsappHref(textosFallo.ayudaMensaje.replace('{paquete}', paquete.nombre)) }
      : null;

    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <CheckoutStepper stepper={checkout.stepper} actual={4} steps={pasos} />
        <div className="mx-auto max-w-xl px-6 pt-8 pb-20 sm:px-8">
          <AvisoFallo
            titulo={titulo}
            motivo={rechazo ? textosFallo.motivos[claveMotivoRechazo(detalle.codigo)] : null}
            lineasDinero={lineasDinero}
            etiquetaBoton={reintentoDirecto ? textosFallo.retryOtraTarjeta : textosFallo.retry}
            onReintentar={reintentoDirecto ? () => void reintentar() : pago.reiniciar}
            ayuda={ayuda}
          />
        </div>
        <CheckoutFooter lang={lang} footer={footer} nav={nav} />
      </div>
    );
  }

  if (pago.fase === 'resumiendo' || pago.fase === 'capturando' || pago.fase === 'confirmando') return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
      <div className="mx-auto max-w-2xl px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
        <p className="text-sm text-foreground">
          {pago.fase === 'resumiendo' ? textos.resuming : feedback.payingWait}
        </p>
        {pago.fase !== 'resumiendo' && <p className="mt-3 text-sm text-muted">{feedback.paySlow}</p>}
      </div>
    </div>
  );

  if (pago.fase === 'pagando') {
    const pasoPago = pago.pagos[pago.indice];
    if (!pasoPago) return null;
    const n = cantidadCargos || pago.pagos.length;
    const monto = formatearPrecio(Number(pasoPago.monto), estado.moneda);
    const etiqueta = nombreEmpresa(pasoPago.empresaSlug);
    const pasosPago = pago.pagos.map((item, indice) => ({
      etiqueta: nombreEmpresa(item.empresaSlug),
      monto: formatearPrecio(Number(item.monto), estado.moneda),
      estado: (indice < pago.indice ? 'hecho' : indice === pago.indice ? 'actual' : 'pendiente') as 'hecho' | 'actual' | 'pendiente',
    }));
    const etiquetaBotonPago = n === 1
      ? textos.payButtonSingle.replace('{amount}', monto)
      : textos.payButton.replace('{amount}', monto).replace('{empresa}', etiqueta)
        .replace('{n}', String(pago.indice + 1)).replace('{total}', String(n));

    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <CheckoutStepper stepper={checkout.stepper} actual={4} steps={pasos} />
        <div className="mx-auto max-w-xl px-6 pt-8 pb-20 sm:px-8">
          <StripePanel
            key={pasoPago.empresaSlug}
            lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
            waiverAccepted={true} onWaiverChange={() => {}} errorWaiver={false}
            lines={[{ label: etiqueta, amount: monto }]} total={monto} amountDueNow={monto}
            moneda={estado.moneda} onMonedaChange={() => {}} usdDisponible={false}
            formaPago="completo" onFormaPagoChange={() => {}} formaPagoDisponible={false}
            codigoPromocional="" onCodigoPromocionalChange={() => {}}
            codigoPromocionalDisponible={false} promoEstado="idle" promoPorcentaje={null}
            phase="payment" error=""
            pago={{ client_secret: pasoPago.clientSecret, publishable_key: pasoPago.publishableKey,
              monto_a_cobrar: pasoPago.monto, moneda: estado.moneda }}
            encabezadoPago={<EncabezadoPago dict={dict} pasos={pasosPago} indice={pago.indice} />}
            etiquetaBotonPago={etiquetaBotonPago}
            onSubmit={() => {}} onPagoConfirmado={pago.onPagoConfirmado}
            onPagoRechazado={pago.onPagoRechazado} onCaptchaToken={() => {}}
          />
        </div>
        <CheckoutFooter lang={lang} footer={footer} nav={nav} />
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
      <div className="mx-auto max-w-3xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8">
        <Link href={`/${lang}/sede/${sedeSlug}`}
          className="mb-6 inline-flex text-sm font-medium text-muted hover:text-foreground">
          {textos.back}
        </Link>
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{textos.title}</h1>
        <p className="mt-2 text-sm text-muted">{paquete.nombre}</p>
        {conUsd && (
          <fieldset className="mt-5 flex items-center gap-3">
            <legend className="sr-only">{checkout.currency.headline}</legend>
            <span className="text-xs text-muted">{checkout.currency.headline}</span>
            <div className="flex overflow-hidden rounded-full border border-border text-xs">
              {(['MXN', 'USD'] as const).map((opcion) => (
                <label key={opcion}
                  className="cursor-pointer px-3 py-1.5 font-medium text-muted transition-colors has-[:checked]:bg-foreground has-[:checked]:text-surface">
                  <input type="radio" name="moneda-pedido" value={opcion}
                    checked={estado.moneda === opcion}
                    onChange={() => despachar({ tipo: 'moneda', valor: opcion })}
                    className="sr-only" />
                  {opcion}
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </div>
      <CheckoutStepper stepper={checkout.stepper} actual={paso} steps={pasos} />
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 pt-6 pb-24 sm:px-8">
        <CheckoutSectionCard
          title={checkout.contactHeadline}
          estado={paso === 1 ? 'activo' : datosEditando ? 'editando' : 'completado'}
          resumen={`${estado.contacto.fullName} · ${estado.contacto.email}`}
          actionLabel={paso > 1 ? datosEditando ? checkout.doneEditing : checkout.changeStep : undefined}
          onAction={paso > 1 ? () => setDatosEditando((actual) => !actual) : undefined}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted">{checkout.phone}</span>
              <span className="relative">
                <Phone size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                <input type="tel" value={estado.contacto.phone}
                  onChange={(event) => despachar({ tipo: 'contacto', cambios: { phone: event.target.value } })}
                  className="w-full border border-border bg-surface py-3 pr-4 pl-11 text-foreground outline-none focus:border-accent" />
              </span>
              {erroresContacto.phone && <FieldError id="pedido-phone-error" mensaje={erroresContacto.phone} />}
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted">{checkout.fullName}</span>
              <span className="relative">
                <User size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                <input type="text" value={estado.contacto.fullName}
                  onChange={(event) => despachar({ tipo: 'contacto', cambios: { fullName: event.target.value } })}
                  className="w-full border border-border bg-surface py-3 pr-4 pl-11 text-foreground outline-none focus:border-accent" />
              </span>
              {erroresContacto.fullName && <FieldError id="pedido-name-error" mensaje={erroresContacto.fullName} />}
            </label>
            <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
              <span className="text-muted">{checkout.email}</span>
              <span className="relative">
                <EnvelopeSimple size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                <input type="email" value={estado.contacto.email}
                  onChange={(event) => despachar({ tipo: 'contacto', cambios: { email: event.target.value } })}
                  className="w-full border border-border bg-surface py-3 pr-4 pl-11 text-foreground outline-none focus:border-accent" />
              </span>
              {erroresContacto.email && <FieldError id="pedido-email-error" mensaje={erroresContacto.email} />}
            </label>
            <div className="sm:col-span-2">
              <TimeField label={checkout.hourLabel} help={booking.timeHelp} value={estado.hora}
                onChange={(valor) => despachar({ tipo: 'hora', valor })} />
            </div>
          </div>
          {paso === 1 && (
            <div className="mt-6 flex justify-end border-t border-border pt-5">
              <button type="button" onClick={confirmarDatos}
                className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground">
                {checkout.confirmStep}
              </button>
            </div>
          )}
        </CheckoutSectionCard>

        {paso >= 2 && (
          <>
            {errorDetalles && <FieldError id="pedido-detalles-error" mensaje={errorDetalles} />}
            {paquete.servicios_asociados.map((componente, indice) => {
              if (indice > gruposCompletados) return null;
              const slug = componente.servicio.slug;
              const tarjeta = indice < gruposCompletados
                ? grupoEditando === indice ? 'editando' : 'completado'
                : 'activo';
              return (
                <GrupoServicio key={componente.id}
                  lang={lang} dict={dict} componente={componente}
                  estado={estado.componentes[slug]}
                  conEncabezadoEmpresa={cantidadCargos > 1}
                  nombreEmpresa={nombreEmpresa(componente.servicio.empresa_slug)}
                  moneda={estado.moneda} inicio={estado.inicio} noches={noches} salida={salida}
                  minDate={minDate} puntos={puntosPorEmpresa[componente.servicio.empresa_slug] ?? []}
                  mostrarInicio={indice === 0} estadoTarjeta={tarjeta}
                  onAccion={() => setGrupoEditando((actual) => actual === indice ? null : indice)}
                  onCompletar={() => confirmarGrupo(indice)}
                  onInicio={(valor) => despachar({ tipo: 'inicio', valor })}
                  onPersonas={(valor) => despachar({ tipo: 'personas', slug, valor })}
                  onExtras={(valor) => despachar({ tipo: 'extras', slug, valor })}
                  onTraslado={(cambios) => despachar({ tipo: 'traslado', slug, cambios })}
                />
              );
            })}
          </>
        )}

        {paso >= 3 && (
          pedido ? (
            <StripePanel
              lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
              waiverAccepted={waiverAccepted}
              onWaiverChange={(valor) => { setWaiverAccepted(valor); if (valor) setErrorWaiver(false); }}
              errorWaiver={errorWaiver}
              lines={cargos.map((cargo) => ({ label: nombreEmpresa(cargo.empresaSlug),
                amount: formatearPrecio(cantidadCargos === 1 ? totalConDescuento : cargo.monto, estado.moneda) }))}
              total={total} amountDueNow={ahora} moneda={estado.moneda}
              onMonedaChange={(valor) => despachar({ tipo: 'moneda', valor })} usdDisponible={false}
              formaPago={estado.formaPago}
              onFormaPagoChange={(valor) => despachar({ tipo: 'formaPago', valor })}
              formaPagoDisponible={paquete.permite_anticipo}
              codigoPromocional={codigoPromocional}
              onCodigoPromocionalChange={(valor) => {
                setCodigoPromocional(valor);
                setPromoEstado(valor.trim() ? 'verificando' : 'idle');
                setPromoPorcentaje(null);
              }}
              codigoPromocionalDisponible={motor === 'reserva'}
              promoEstado={promoEstado} promoPorcentaje={promoPorcentaje}
              phase={pago.fase === 'enviando' ? 'submitting' : pago.error ? 'error' : 'form'}
              error={pago.error} pago={null}
              avisoCargos={cantidadCargos > 1 ? (
                <div className="mt-5 border-t border-border pt-5">
                  <AvisoCargos dict={dict}
                    cargos={cargos.map((cargo) => ({ etiqueta: nombreEmpresa(cargo.empresaSlug), monto: formatearPrecio(cargo.monto, estado.moneda) }))}
                    total={total} />
                </div>
              ) : undefined}
              etiquetaBotonEnvio={cantidadCargos > 1
                ? textos.continueToPayment.replace('{total}', String(cantidadCargos)) : undefined}
              onSubmit={enviar} onPagoConfirmado={pago.onPagoConfirmado}
              onPagoRechazado={pago.onPagoRechazado}
              onCaptchaToken={(token) => { captcha.current = token; }}
            />
          ) : (
            <ErrorBlock mensaje={feedback.error.no_disponible}
              ayudaTitulo={feedback.helpTitle} ayudaCta={feedback.helpCta} ayudaMensaje={ayudaMensaje} />
          )
        )}
      </main>
      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );
}
