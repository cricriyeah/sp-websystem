'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { AyudaFlotante } from '@/components/checkout/ayuda-flotante';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { CamposContacto } from '@/components/checkout/campos-contacto';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { useAyudaContextual } from '@/components/checkout/use-ayuda-contextual';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CheckoutStepper } from '@/components/checkout-stepper';
import { ErrorBlock } from '@/components/error-block';
import { FieldError } from '@/components/field-error';
import { SiteHeader } from '@/components/site-header';
import { WaitNotice } from '@/components/wait-notice';
import { PeopleStepper } from '@/components/people-stepper';
import { StripePanel } from '@/components/stripe-panel';
import { TimeField } from '@/components/time-field';
import { validarCodigoPromocional, type PaqueteCatalogo, type PuntoEncuentro, type TrasladosCatalogo } from '@/lib/api';
import { fechaDeComponente, fechaSalida, nochesDelPaquete } from '@/lib/calendario-paquete';
import { formatHour, fromLocalISODate } from '@/lib/dates';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { mensajeDeAyuda, mensajeDeError } from '@/lib/errores';
import { claveMotivoRechazo, ofreceAyuda, pagosRetenidosAntes } from '@/lib/fallo-pago';
import { horasDePaquete } from '@/lib/horario-servicio';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import { estadoDeTarjeta, numeroDePaso, type PasoId } from '@/lib/pasos-checkout';
import {
  calcularPedido, maxPersonasPaquete, montoInicial, servicioPrincipalPaquete, trasladoFijoAeropuerto, usdDisponible,
} from '@/lib/pedido-paquete';
import { armarPayloadOrden, armarPayloadReserva, zonaEfectivaDeTraslado } from '@/lib/pedido-payload';
import { erroresPersonalizaciones } from '@/lib/personalizaciones';
import { calcularBasePaquete } from '@/lib/precio-paquete';
import { leerRef } from '@/lib/ref';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { AvisoCargos } from './aviso-cargos';
import { AvisoFallo } from './aviso-fallo';
import { EncabezadoPago } from './encabezado-pago';
import { FechaPaquete } from './fecha-paquete';
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
  retomarCheckoutId?: string;
};

export function PedidoPaquete({ lang, dict, paquete, sedeSlug, tarifasPorEmpresa, puntosPorEmpresa, minDate, retomarCheckoutId }: Props) {
  const { checkout, booking, feedback, pedido: textos, nav, footer, traslados } = dict;
  const motor = paquete.es_cruza_empresa ? 'orden' : 'reserva';
  const trasladoFijo = trasladoFijoAeropuerto(paquete);
  const [estado, despachar] = usePedidoEstado(paquete, {
    moneda: 'MXN',
    puntoInicial: (empresa) => puntosPorEmpresa[empresa]?.[0]?.id ?? null,
  });
  const captcha = useRef('');
  const [actual, setActual] = useState<PasoId>('viaje');
  const [editando, setEditando] = useState<PasoId | null>(null);
  const tarjeta = (id: PasoId) => estadoDeTarjeta(id, actual, editando);
  const ayuda = useAyudaContextual();
  const [gruposCompletados, setGruposCompletados] = useState(0);
  const [grupoEditando, setGrupoEditando] = useState<number | null>(null);
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [errorWaiver, setErrorWaiver] = useState(false);
  const [erroresContacto, setErroresContacto] = useState<Partial<Record<'fullName' | 'phone' | 'email', string>>>({});
  const [errorViaje, setErrorViaje] = useState('');
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
  const conUsd = usdDisponible(paquete);
  const maxPersonas = paquete.precio_depende_de_personas ? maxPersonasPaquete(paquete) : null;
  const slugPrincipal = paquete.precio_depende_de_personas ? servicioPrincipalPaquete(paquete)?.servicio.slug : undefined;
  const primerServicio = slugPrincipal ?? paquete.servicios_asociados[0]?.servicio.slug;
  const personasPaquete = primerServicio ? estado.componentes[primerServicio]?.personas ?? 1 : 1;
  const ancla = aMoneda(paquete.precio_ancla, estado.moneda, paquete.tipo_cambio_usd);
  const extra = aMoneda(paquete.precio_persona_extra, estado.moneda, paquete.tipo_cambio_usd);
  const anclaMostrada = formatearPrecio(ancla, estado.moneda);
  const precioBaseGrupo = calcularBasePaquete(paquete, estado.moneda, personasPaquete);
  const precioPersonas = (personasPaquete === 1 ? textos.peoplePriceOne : textos.peoplePrice)
    .replace('{n}', String(personasPaquete))
    .replace('{precio}', formatearPrecio(precioBaseGrupo, estado.moneda))
    .replace('{price}', formatearPrecio(precioBaseGrupo, estado.moneda));
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
  const totalConMoneda = totalConDescuento === null ? null : `${total} ${estado.moneda}`;
  const totalMovil = paquete.precio_depende_de_personas ? totalConMoneda ?? undefined : undefined;
  const ahora = totalConDescuento !== null ? formatearPrecio(
    paquete.permite_anticipo
      ? montoInicial(totalConDescuento, estado.formaPago, paquete.porcentaje_anticipo)
      : totalConDescuento,
    estado.moneda,
  ) : '—';
  const ayudaMensaje = mensajeDeAyuda(paquete.pide_hora ? feedback.helpMessage : feedback.helpMessageNoTime, {
    fecha: estado.inicio ?? minDate,
    hora: estado.hora,
    personas: personasPaquete,
  });
  const empresas = [...new Set(paquete.servicios_asociados.map((c) => nombreEmpresa(c.servicio.empresa_slug)))];
  const detalleCompra = [
    paquete.sede,
    empresas.join(' + '),
    noches !== null ? checkout.purchaseNights.replace('{n}', String(noches)) : null,
  ].filter(Boolean).join(' · ');
  const resumenViaje = [
    estado.inicio ? formatearFecha(estado.inicio) : null,
    paquete.pide_hora && estado.hora ? formatHour(estado.hora) : null,
    paquete.precio_depende_de_personas
      ? `${personasPaquete} ${personasPaquete === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`
      : null,
  ].filter(Boolean).join(' · ');
  const lineasViaje = [
    estado.inicio ? { etiqueta: checkout.summary.date, valor: formatearFecha(estado.inicio) } : null,
    salida && noches !== null ? { etiqueta: checkout.summary.checkOut, valor: formatearFecha(salida) } : null,
    paquete.pide_hora && estado.hora ? { etiqueta: checkout.summary.time, valor: formatHour(estado.hora) } : null,
    paquete.precio_depende_de_personas
      ? { etiqueta: checkout.summary.people, valor: String(personasPaquete) }
      : null,
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);

  const pago = usePagoPedido({
    motor,
    sedeSlug,
    empresaSlug: paquete.empresa_lider_slug,
    paqueteSlug: paquete.slug,
    paqueteNombre: paquete.nombre,
    retomarCheckoutId,
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

  const confirmarViaje = () => {
    if (!estado.inicio) {
      setErrorViaje(traslados.errors.seleccionaFecha);
      ayuda.tropezar('validacion');
      return;
    }
    setErrorViaje('');
    setEditando(null);
    setActual((a) => (a === 'viaje' ? 'contacto' : a));
  };

  const confirmarDatos = () => {
    if (!validarDatos()) {
      ayuda.tropezar('validacion');
      return;
    }
    setEditando(null);
    setActual((a) => (a === 'contacto' ? 'detalles' : a));
  };

  const errorDeGrupo = (indice: number): string => {
    if (!estado.inicio) return traslados.errors.seleccionaFecha;
    const item = paquete.servicios_asociados[indice];
    const actual = estado.componentes[item.servicio.slug];
    const errores = erroresPersonalizaciones(item.servicio.personalizaciones, actual.extras);
    const primerError = Object.values(errores)[0];
    if (primerError) return checkout.personalizacionErrors[primerError];
    const t = actual.traslado;
    if (t && trasladoFijo) {
      if (!t.aeropuerto) return textos.airportError;
    } else if (t) {
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

  // La actividad principal de un paquete que depende de personas se elige en
  // Viaje; si no lleva extras, no necesita una tarjeta de detalles adicional.
  const grupoOculto = (indice: number) => {
    const componente = paquete.servicios_asociados[indice];
    return paquete.precio_depende_de_personas && indice > 0 && componente.servicio.slug === slugPrincipal
      && componente.servicio.personalizaciones.length === 0;
  };

  const confirmarGrupo = (indice: number) => {
    const error = errorDeGrupo(indice);
    if (error) {
      ayuda.tropezar('validacion');
      if (!estado.inicio) {
        setErrorViaje(error);
        setErrorDetalles('');
        setEditando('viaje');
      } else {
        setErrorDetalles(error);
      }
      return;
    }
    setErrorDetalles('');
    let siguiente = indice + 1;
    while (siguiente < paquete.servicios_asociados.length && grupoOculto(siguiente)) siguiente += 1;
    setGruposCompletados(siguiente);
    if (siguiente >= paquete.servicios_asociados.length) setActual('pago');
  };

  const enviar = () => {
    if (actual !== 'pago') return;
    if (!validarDatos()) {
      setEditando('contacto');
      ayuda.tropezar('validacion');
      return;
    }
    for (let indice = 0; indice < paquete.servicios_asociados.length; indice++) {
      const error = errorDeGrupo(indice);
      if (error) {
        if (!estado.inicio) {
          setErrorViaje(error);
          setErrorDetalles('');
          setEditando('viaje');
        } else {
          setErrorDetalles(error);
          setGrupoEditando(indice);
        }
        return;
      }
    }
    if (!waiverAccepted) {
      ayuda.tropezar('validacion');
      return setErrorWaiver(true);
    }
    if (!pedido) return setErrorDetalles(feedback.error.no_disponible);
    setErrorDetalles('');
    void pago.enviar();
  };

  if (pago.fase === 'exito') return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{textos.success.title}</h1>
        <p className="text-sm text-muted">{textos.success.body}</p>
        <div className="w-full border border-border bg-card p-5 text-left">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            {textos.success.componentsHeadline}
          </p>
          <ul className="flex flex-col gap-2">
            {paquete.servicios_asociados.map((item) => (
              <li key={item.id} className="flex flex-wrap justify-between gap-2 text-sm text-foreground">
                <span>{item.servicio.nombre}</span>
                <span className="text-muted">
                  {formatearFecha(fechaDeComponente(estado.inicio ?? minDate, item.dia_estancia))}
                  {' · '}{estado.componentes[item.servicio.slug]?.personas ?? item.personas_incluidas}{' '}
                  {(estado.componentes[item.servicio.slug]?.personas ?? item.personas_incluidas) === 1
                    ? checkout.peopleUnit.one : checkout.peopleUnit.other}
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
    if (!llegoAlPago) setEditando('viaje'); // p. ej. ya no hay cupo: se abre la fecha para cambiarla
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
        <div aria-hidden className="h-[calc(1.5rem_+_var(--nav-alto))]" />
        <CheckoutStepper stepper={checkout.stepper} actual={4} totalMovil={totalMovil} />
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
        <WaitNotice
          mensaje={pago.fase === 'resumiendo' ? textos.resuming : feedback.payingWait}
          mensajeLento={pago.fase === 'resumiendo' ? undefined : feedback.paySlow}
        />
      </div>
    </div>
  );

  if (pago.fase === 'pagando') {
    const pasoPago = pago.pagos[pago.indice];
    if (!pasoPago) return null;
    const n = cantidadCargos || pago.pagos.length;
    const monto = formatearPrecio(Number(pasoPago.monto), estado.moneda);
    const totalPago = formatearPrecio(Number(pasoPago.precioTotal ?? pasoPago.monto), estado.moneda);
    const etiqueta = nombreEmpresa(pasoPago.empresaSlug);
    const pasosPago = pago.pagos.map((item, indice) => ({
      etiqueta: nombreEmpresa(item.empresaSlug),
      monto: formatearPrecio(Number(item.monto), estado.moneda),
      estado: (indice < pago.indice ? 'hecho' : indice === pago.indice ? 'actual' : 'pendiente') as 'hecho' | 'actual' | 'pendiente',
    }));
    const etiquetaBotonPago = n === 1
      ? paquete.precio_depende_de_personas
        ? (personasPaquete === 1 ? textos.payOne : textos.payPeople.replace('{n}', String(personasPaquete)))
          .replace('{amount}', `${monto} ${estado.moneda}`)
        : textos.payButtonSingle.replace('{amount}', monto)
      : textos.payButton.replace('{amount}', monto).replace('{empresa}', etiqueta)
        .replace('{n}', String(pago.indice + 1)).replace('{total}', String(n));

    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <div aria-hidden className="h-[calc(1.5rem_+_var(--nav-alto))]" />
        <CheckoutStepper stepper={checkout.stepper} actual={4} totalMovil={totalMovil} />
        <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
          <div className="flex min-w-0 flex-col gap-6">
            <CheckoutSectionCard title={checkout.contactHeadline} estado="completado"
              resumen={`${estado.contacto.fullName} · ${estado.contacto.email}`}>
              {null}
            </CheckoutSectionCard>
            {paquete.servicios_asociados.map((item) => {
              const personas = estado.componentes[item.servicio.slug]?.personas ?? item.personas_incluidas;
              return (
                <CheckoutSectionCard key={item.id} title={item.servicio.nombre} estado="completado"
                  resumen={`${nombreEmpresa(item.servicio.empresa_slug)} · ${formatearFecha(fechaDeComponente(estado.inicio ?? minDate, item.dia_estancia))} · ${personas} ${personas === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`}>
                  {null}
                </CheckoutSectionCard>
              );
            })}
          </div>
          <div className="min-w-0">
            <StripePanel
              key={pasoPago.empresaSlug}
              lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
              waiverAccepted={true} onWaiverChange={() => {}} errorWaiver={false}
              lines={[{ label: etiqueta, amount: totalPago }]} total={totalPago} amountDueNow={monto}
              moneda={estado.moneda} onMonedaChange={() => {}} usdDisponible={false}
              formaPago="completo" onFormaPagoChange={() => {}} formaPagoDisponible={false}
              codigoPromocional="" onCodigoPromocionalChange={() => {}}
              codigoPromocionalDisponible={false} promoEstado="idle" promoPorcentaje={null}
              phase="payment" error=""
              pago={{ client_secret: pasoPago.clientSecret, publishable_key: pasoPago.publishableKey }}
              encabezadoPago={<EncabezadoPago dict={dict} pasos={pasosPago} indice={pago.indice} />}
              etiquetaBotonPago={etiquetaBotonPago}
              onSubmit={() => {}} onPagoConfirmado={pago.onPagoConfirmado}
              onPagoRechazado={pago.onPagoRechazado} onCaptchaToken={() => {}}
            />
          </div>
        </main>
        <CheckoutFooter lang={lang} footer={footer} nav={nav} />
      </div>
    );
  }

  return (
    <>
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
        stepper={{ actual: numeroDePaso(actual), totalMovil }}
        pasos={
          <>
            <CheckoutSectionCard
              title={checkout.tripHeadline}
              estado={tarjeta('viaje') as 'activo' | 'editando' | 'completado'}
              resumen={resumenViaje}
              actionLabel={tarjeta('viaje') === 'completado' ? checkout.changeStep : tarjeta('viaje') === 'editando' ? checkout.doneEditing : undefined}
              onAction={tarjeta('viaje') === 'activo' ? undefined : () => setEditando((e) => (e === 'viaje' ? null : 'viaje'))}
              pie={tarjeta('viaje') === 'activo' ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso> : undefined}
            >
              <ContenidoViaje
                fecha={
                  <FechaPaquete
                    lang={lang}
                    label={textos.startLabel}
                    value={estado.inicio}
                    onChange={(valor) => despachar({ tipo: 'inicio', valor })}
                    minDate={minDate}
                    chooseLabel={textos.chooseStart}
                    viewMonthLabel={textos.viewMonth}
                    hideMonthLabel={textos.hideMonth}
                    previousWeekLabel={textos.previousWeek}
                    nextWeekLabel={textos.nextWeek}
                    previousMonthLabel={booking.prevMonth}
                    nextMonthLabel={booking.nextMonth}
                    personas={personasPaquete}
                    fullLabel={checkout.dayFull}
                  />
                }
                hora={paquete.pide_hora ? (
                  <TimeField
                    label={checkout.hourLabel}
                    help={booking.timeHelp}
                    value={estado.hora}
                    availableHours={horasDePaquete(paquete)}
                    onChange={(valor) => despachar({ tipo: 'hora', valor })}
                  />
                ) : undefined}
                personas={paquete.precio_depende_de_personas && maxPersonas !== null ? (
                  <PeopleStepper
                    label={textos.peopleQuestion}
                    maxNotice={(tieneWhatsapp ? textos.morePeople : textos.morePeopleOffline).replace('{max}', String(maxPersonas))}
                    value={personasPaquete}
                    maxPeople={maxPersonas}
                    minPeople={1}
                    onChange={(valor) => {
                      if (slugPrincipal) despachar({ tipo: 'personasPaquete', slugPrincipal, valor });
                    }}
                    onMaxAttempt={() => ayuda.tropezar('tope-personas')}
                  />
                ) : undefined}
                nota={
                  <>
                    {noches !== null && salida && (
                      <p>{textos.nightsNote.replace('{n}', String(noches)).replace('{fecha}', formatearFecha(salida))}</p>
                    )}
                    {paquete.precio_depende_de_personas && (
                      <>
                        <p className="font-medium text-foreground">
                          {anclaMostrada} {estado.moneda}{' '}
                          {paquete.estrategia_precio === 'por_persona'
                            ? textos.perPerson
                            : textos.perGroup.replace('{n}', String(paquete.personas_precio_base))}
                        </p>
                        {paquete.estrategia_precio === 'por_grupo' && extra !== null && (
                          <p>{textos.extraPerson.replace('{precio}', formatearPrecio(extra, estado.moneda))}</p>
                        )}
                        <p>{precioPersonas}</p>
                      </>
                    )}
                  </>
                }
              />
              {errorViaje && <FieldError id="pedido-viaje-error" mensaje={errorViaje} />}
            </CheckoutSectionCard>

            {tarjeta('contacto') !== 'oculto' && (
              <CheckoutSectionCard
                title={checkout.contactHeadline}
                estado={tarjeta('contacto') as 'activo' | 'editando' | 'completado'}
                resumen={`${estado.contacto.fullName} · ${estado.contacto.email}`}
                actionLabel={tarjeta('contacto') === 'completado' ? checkout.changeStep : tarjeta('contacto') === 'editando' ? checkout.doneEditing : undefined}
                onAction={tarjeta('contacto') === 'activo' ? undefined : () => setEditando((e) => (e === 'contacto' ? null : 'contacto'))}
                pie={tarjeta('contacto') === 'activo' ? <BotonPaso onClick={confirmarDatos}>{checkout.confirmStep}</BotonPaso> : undefined}
              >
                <CamposContacto
                  idPrefijo="pedido"
                  valores={estado.contacto}
                  errores={erroresContacto}
                  etiquetas={{ phone: checkout.phone, fullName: checkout.fullName, email: checkout.email }}
                  onCambio={(campo, valor) => despachar({ tipo: 'contacto', cambios: { [campo]: valor } })}
                />
              </CheckoutSectionCard>
            )}

            {tarjeta('detalles') !== 'oculto' && (
              <>
                {errorDetalles && <FieldError id="pedido-detalles-error" mensaje={errorDetalles} />}
                {paquete.servicios_asociados.map((componente, indice) => {
                  if (indice > gruposCompletados || grupoOculto(indice)) return null;
                  const slug = componente.servicio.slug;
                  const estadoGrupo = indice < gruposCompletados
                    ? grupoEditando === indice ? 'editando' : 'completado'
                    : 'activo';
                  return (
                    <GrupoServicio
                      key={componente.id}
                      lang={lang}
                      dict={dict}
                      componente={componente}
                      precioDependeDePersonas={paquete.precio_depende_de_personas}
                      esActividadPrincipal={slug === slugPrincipal}
                      personasMax={personasPaquete}
                      trasladoFijo={trasladoFijo}
                      estado={estado.componentes[slug]}
                      conEncabezadoEmpresa={cantidadCargos > 1}
                      nombreEmpresa={nombreEmpresa(componente.servicio.empresa_slug)}
                      moneda={estado.moneda}
                      tipoCambio={paquete.tipo_cambio_usd}
                      inicio={estado.inicio}
                      noches={noches}
                      salida={salida}
                      puntos={puntosPorEmpresa[componente.servicio.empresa_slug] ?? []}
                      estadoTarjeta={estadoGrupo}
                      onAccion={() => setGrupoEditando((a) => a === indice ? null : indice)}
                      onCompletar={() => confirmarGrupo(indice)}
                      onTope={() => ayuda.tropezar('tope-personas')}
                      onPersonas={(valor) => despachar(paquete.precio_depende_de_personas && slugPrincipal
                        ? { tipo: 'personasLogistica', slug, slugPrincipal, valor }
                        : { tipo: 'personas', slug, valor })}
                      onExtras={(valor) => despachar({ tipo: 'extras', slug, valor })}
                      onTraslado={(cambios) => despachar({ tipo: 'traslado', slug, cambios })}
                    />
                  );
                })}
              </>
            )}
          </>
        }
        pedido={pedido ? (
          <StripePanel
            lang={lang} checkout={checkout} feedback={feedback} ayudaMensaje={ayudaMensaje}
            waiverAccepted={waiverAccepted}
            onWaiverChange={(valor) => { setWaiverAccepted(valor); if (valor) setErrorWaiver(false); }}
            errorWaiver={errorWaiver}
            lines={cargos.map((cargo) => ({ label: nombreEmpresa(cargo.empresaSlug),
              amount: formatearPrecio(cantidadCargos === 1 ? totalConDescuento : cargo.monto, estado.moneda) }))}
            lineasViaje={lineasViaje}
            pagoVisibleMovil={actual === 'pago'}
            total={total} amountDueNow={ahora} moneda={estado.moneda}
            onMonedaChange={(valor) => despachar({ tipo: 'moneda', valor })} usdDisponible={conUsd}
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
            submitDisabled={actual !== 'pago'}
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
        )}
      />
      <AyudaFlotante
        visible={ayuda.visible}
        etiqueta={feedback.floatingHelp.label}
        cerrarLabel={feedback.floatingHelp.dismiss}
        mensaje={ayuda.motivo === 'tope-personas' && maxPersonas !== null
          ? feedback.floatingHelp.messageMaxPeople.replace('{name}', paquete.nombre).replace('{max}', String(maxPersonas))
          : feedback.floatingHelp.messageValidation
              .replace('{date}', formatearFecha(estado.inicio ?? minDate))
              .replace('{people}', String(personasPaquete))}
        onDescartar={ayuda.descartar}
      />
    </>
  );
}
