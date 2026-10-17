'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { AyudaFlotante } from '@/components/checkout/ayuda-flotante';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { BloqueContacto } from '@/components/checkout/bloques/bloque-contacto';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { ItemPaso } from '@/components/checkout/item-paso';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { useAyudaContextual } from '@/components/checkout/use-ayuda-contextual';
import { useScrollAlFoco } from '@/components/checkout/use-scroll-al-foco';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import { precargarFormularioPago } from '@/components/checkout/pago/pago-diferido';
import { validarCodigoPromocional, type PaqueteCatalogo, type PuntoEncuentro, type TrasladosCatalogo } from '@/lib/api';
import { fechaSalida, nochesDelPaquete } from '@/lib/calendario-paquete';
import { fromLocalISODate } from '@/lib/dates';
import { mensajeDeAyuda, mensajeDeError } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import {
  estadoDeTarjeta, estadoVisible, numeroDePaso, unidaConAnterior, type EstadoTarjeta, type EstadoVisible, type PasoId,
} from '@/lib/pasos-checkout';
import {
  calcularPedido, maxPersonasPaquete, montoInicial, servicioPrincipalPaquete, trasladoFijoAeropuerto, usdDisponible,
} from '@/lib/pedido-paquete';
import { armarPayloadOrden, armarPayloadReserva, zonaEfectivaDeTraslado } from '@/lib/pedido-payload';
import { leerRef } from '@/lib/ref';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { BloqueViajePaquete } from './bloque-viaje-paquete';
import { GrupoServicio } from './grupo-servicio';
import { PantallaEspera } from './pantalla-espera';
import { PantallaExito } from './pantalla-exito';
import { PantallaFallo } from './pantalla-fallo';
import { PanelPedidoPaquete } from './panel-pedido-paquete';
import { PantallaPago } from './pantalla-pago';
import { armarResumenPaquete } from './resumen-paquete';
import { usePagoPedido } from './use-pago-pedido';
import { usePedidoEstado } from './use-pedido-estado';
import { erroresDeContacto, errorDeGrupoPaquete, type ErroresContacto } from './validacion-paquete';

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
  const { checkout, feedback, pedido: textos, traslados } = dict;
  const motor = paquete.es_cruza_empresa ? 'orden' : 'reserva';
  const trasladoFijo = trasladoFijoAeropuerto(paquete);
  const [estado, despachar] = usePedidoEstado(paquete, {
    moneda: 'MXN',
    puntoInicial: (empresa) => puntosPorEmpresa[empresa]?.[0]?.id ?? null,
  });
  const captcha = useRef('');
  // Donde se pinta la tarjeta "Cómo pagas" (el cuarto paso, en la columna de pasos).
  const [destinoTarjetaPago, setDestinoTarjetaPago] = useState<HTMLElement | null>(null);
  const [actual, setActual] = useState<PasoId>('viaje');
  const [editando, setEditando] = useState<PasoId | null>(null);
  const tarjeta = (id: PasoId) => estadoDeTarjeta(id, actual, editando);
  const ayuda = useAyudaContextual();

  // Al llegar a "Cómo pagas" se pide ya el formulario de tarjeta (y con él Stripe.js):
  // para cuando se crea el pago, el chunk está listo. Solo en el cliente.
  useEffect(() => {
    if (actual === 'pago') precargarFormularioPago().catch(() => {});
  }, [actual]);
  const [gruposCompletados, setGruposCompletados] = useState(0);
  const [grupoEditando, setGrupoEditando] = useState<number | null>(null);
  // Cuando el cliente cambia de paso (confirma uno o reabre una respuesta) la
  // tarjeta en foco se trae a la vista solo si hace falta.
  useScrollAlFoco(`${actual}|${editando}|${gruposCompletados}|${grupoEditando}`);
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  // Cambia para remontar el StripePanel con su Turnstile: el token es de un solo uso.
  const [captchaKey, setCaptchaKey] = useState(0);
  const [errorWaiver, setErrorWaiver] = useState(false);
  const [erroresContacto, setErroresContacto] = useState<ErroresContacto>({});
  const [errorViaje, setErrorViaje] = useState('');
  const [errorDetalles, setErrorDetalles] = useState('');
  const [codigoPromocional, setCodigoPromocional] = useState('');
  const [promoEstado, setPromoEstado] = useState<'idle' | 'verificando' | 'valido' | 'invalido'>('idle');
  const [promoPorcentaje, setPromoPorcentaje] = useState<string | null>(null);
  // Lo que resta el codigo segun el servidor (misma funcion que `crear-pago`).
  const [promoDescuento, setPromoDescuento] = useState<{ valor: number; base: number | null } | null>(null);

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
  const cargos = pedido?.cargos ?? [];
  const cantidadCargos = cargos.length;
  const nombreEmpresa = (slug: string) => slug === paquete.empresa_lider_slug
    ? paquete.empresa_lider
    : slug.split('-').map((parte) => parte.charAt(0).toUpperCase() + parte.slice(1)).join(' ');
  const formatearFecha = (iso: string) => new Intl.DateTimeFormat(intlLocale(lang), {
    day: 'numeric', month: 'long', year: 'numeric',
  }).format(fromLocalISODate(iso));
  // El descuento que se muestra es el que calcula el servidor; el calculo local
  // solo cubre el instante entre cambiar el subtotal y recibir la respuesta.
  const descuento = pedido && motor === 'reserva' && promoEstado === 'valido' && promoPorcentaje
    ? Math.min(pedido.total, promoDescuento && promoDescuento.base === pedido.total ? promoDescuento.valor : Math.round(pedido.total * Number(promoPorcentaje) / 100 * 100) / 100)
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
  const { detalleCompra, resumenViaje, lineasViaje, lineasContacto, lineaPunto } = armarResumenPaquete({
    paquete, inicio: estado.inicio, hora: estado.hora, contacto: estado.contacto, personasPaquete, salida, noches,
    checkout, traslados, puntosPorEmpresa, nombreEmpresa, formatearFecha,
  });

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
    mensajeMontoDistinto: (monto) => checkout.montoDistinto
      .replace('{monto}', formatearPrecio(Number(monto), estado.moneda)),
    armarPayload: (checkoutId) => {
      const args = {
        checkoutId, paquete, componentes: estado.componentes, inicio: estado.inicio ?? minDate,
        hora: estado.hora, moneda: estado.moneda, contacto: estado.contacto, ref: leerRef(),
        zonaDePunto,
      };
      return motor === 'orden' ? armarPayloadOrden(args) : armarPayloadReserva(args);
    },
  });
  // Al pasar a pagar (o al siguiente pago de una orden) la tarjeta de pago se trae a la vista.
  useScrollAlFoco(`pago|${pago.fase}|${pago.indice}`);

  const subtotalPromo = pedido?.total ?? null;

  useEffect(() => {
    if (motor !== 'reserva' || !codigoPromocional.trim() || !estado.contacto.email.trim()) return;
    let activo = true;
    const timer = setTimeout(() => {
      validarCodigoPromocional(codigoPromocional.trim(), estado.contacto.email.trim(), paquete.empresa_lider_slug, subtotalPromo)
        .then((resultado) => {
          if (!activo) return;
          setPromoEstado(resultado.valido ? 'valido' : 'invalido');
          setPromoPorcentaje(resultado.porcentaje_descuento);
          setPromoDescuento(resultado.descuento === null ? null : { valor: Number(resultado.descuento), base: subtotalPromo });
        })
        .catch(() => {
          if (activo) setPromoEstado('idle');
        });
    }, 400);
    return () => { activo = false; clearTimeout(timer); };
  }, [motor, codigoPromocional, estado.contacto.email, paquete.empresa_lider_slug, subtotalPromo]);

  const validarDatos = () => {
    const errores = erroresDeContacto(estado.contacto, checkout);
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

  const errorDeGrupo = (indice: number): string => errorDeGrupoPaquete({
    indice, paquete, componentes: estado.componentes, inicio: estado.inicio, trasladoFijo, noches, zonaDePunto,
    textos, traslados, checkout,
  });

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
    <PantallaExito
      lang={lang}
      dict={dict}
      sedeSlug={sedeSlug}
      paquete={paquete}
      inicio={estado.inicio ?? minDate}
      componentes={estado.componentes}
      formatearFecha={formatearFecha}
    />
  );

  // Tras un fallo en esta misma sesión el formulario sigue en memoria: se reintenta con una
  // orden nueva directo al pago. Tras una recarga no hay datos que conservar: se vuelve al formulario.
  const reintentar = async () => {
    const llegoAlPago = await pago.reintentar();
    if (!llegoAlPago) setEditando('viaje'); // p. ej. ya no hay cupo: se abre la fecha para cambiarla
  };

  // Cruza-empresa: cada cobro es un paso del stepper y su cifra es la de ese
  // cobro (no el total del pedido), para que coincida con el botón de pagar.
  // Con un solo cobro el stepper queda de 4 pasos, como siempre.
  const stepperPagos = (indicePago: number, monto?: number) => {
    if (cantidadCargos <= 1) return null;
    const dato = monto ?? cargos[indicePago]?.monto;
    return {
      steps: [
        checkout.stepper.trip, checkout.stepper.contact, checkout.stepper.extras,
        ...cargos.map((cargo, i) => checkout.stepper.paymentNumbered
          .replace('{n}', String(i + 1)).replace('{empresa}', nombreEmpresa(cargo.empresaSlug))),
      ],
      etiquetasCortas: [
        checkout.stepper.trip, checkout.stepper.contact, checkout.stepper.extras,
        ...cargos.map((_, i) => checkout.stepper.paymentShort.replace('{n}', String(i + 1))),
      ],
      actual: 4 + indicePago,
      totalMovil: dato !== undefined ? `${formatearPrecio(dato, estado.moneda)} ${estado.moneda}` : undefined,
      // "Pagas ahora": con varios cobros la cifra del paso no es el total.
      rotulo: dato !== undefined ? checkout.stepper.payNow : undefined,
      totalGeneral: totalConMoneda ?? undefined,
    };
  };

  // Volver al formulario tras una cancelacion: checkout_id nuevo (lo genera el hook) y Turnstile nuevo.
  const reiniciarPedido = () => {
    captcha.current = '';
    setCaptchaKey((k) => k + 1);
    pago.reiniciar();
  };

  if (pago.fase === 'fallo') return (
    <PantallaFallo
      lang={lang}
      dict={dict}
      sedeSlug={sedeSlug}
      paquete={paquete}
      motor={motor}
      moneda={estado.moneda}
      pagos={pago.pagos}
      fallo={pago.fallo}
      falloEnVivo={pago.falloEnVivo}
      fallos={pago.fallos}
      nombreEmpresa={nombreEmpresa}
      stepper={stepperPagos(pago.fallo?.indice ?? 0) ?? { actual: 4, totalMovil }}
      onReintentarDirecto={reintentar}
      onReiniciar={reiniciarPedido}
    />
  );

  if (pago.fase === 'resumiendo' || pago.fase === 'capturando' || pago.fase === 'confirmando') return (
    <PantallaEspera
      lang={lang}
      dict={dict}
      sedeSlug={sedeSlug}
      fase={pago.fase}
      confirmandoLargo={pago.confirmandoLargo}
    />
  );

  if (pago.fase === 'pagando') return (
    <PantallaPago
      lang={lang}
      dict={dict}
      sedeSlug={sedeSlug}
      paquete={paquete}
      motor={motor}
      moneda={estado.moneda}
      pago={pago}
      cantidadCargos={cantidadCargos}
      nombreEmpresa={nombreEmpresa}
      personasPaquete={personasPaquete}
      stepperPagos={stepperPagos}
      totalMovil={totalMovil}
      total={total}
      totalConMoneda={totalConMoneda}
      ayudaMensaje={ayudaMensaje}
      detalleCompra={detalleCompra}
      resumenViaje={resumenViaje}
      lineasViaje={lineasViaje}
      lineasContacto={lineasContacto}
      contacto={estado.contacto}
      componentes={estado.componentes}
      inicio={estado.inicio ?? minDate}
      formatearFecha={formatearFecha}
      lineaPunto={lineaPunto}
      destinoTarjetaPago={destinoTarjetaPago}
      setDestinoTarjetaPago={setDestinoTarjetaPago}
    />
  );

  // Un solo foco abierto: si el cliente reabrió una respuesta, la tarjeta activa
  // se pliega a un renglón "pendiente" hasta que termine de corregirla.
  const hayEdicion = editando !== null || grupoEditando !== null;
  const estadoDeGrupo = (indice: number): EstadoTarjeta =>
    indice < gruposCompletados ? (grupoEditando === indice ? 'editando' : 'completado') : 'activo';
  const estadoViaje = estadoVisible(tarjeta('viaje') as EstadoTarjeta, hayEdicion);
  const estadoContacto: EstadoVisible = estadoVisible(
    (tarjeta('contacto') === 'oculto' ? 'activo' : tarjeta('contacto')) as EstadoTarjeta, hayEdicion,
  );
  // Orden exacto en el que se pintan las tarjetas, para saber cuáles van pegadas.
  const secuencia: EstadoVisible[] = [estadoViaje];
  if (tarjeta('contacto') !== 'oculto') secuencia.push(estadoContacto);
  const posicionDeGrupo = new Map<number, number>();
  if (tarjeta('detalles') !== 'oculto') {
    paquete.servicios_asociados.forEach((_, indice) => {
      if (indice > gruposCompletados || grupoOculto(indice)) return;
      posicionDeGrupo.set(indice, secuencia.length);
      secuencia.push(estadoVisible(estadoDeGrupo(indice), hayEdicion));
    });
  }

  // El error de detalles vive en la tarjeta de grupo que está en foco (la que lo
  // causó, pegado a su CTA); si no hay ninguna en foco, va debajo de la lista.
  const indiceGrupoEnFoco = [...posicionDeGrupo.entries()]
    .find(([, posicion]) => secuencia[posicion] === 'activo' || secuencia[posicion] === 'editando')?.[0] ?? null;

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
        stepper={(actual === 'pago' ? stepperPagos(0) : null) ?? {
          actual: numeroDePaso(actual), totalMovil,
          steps: cantidadCargos > 1 ? stepperPagos(0)?.steps : undefined,
          etiquetasCortas: cantidadCargos > 1 ? stepperPagos(0)?.etiquetasCortas : undefined,
        }}
        pasos={
          <>
            <ItemPaso unida={unidaConAnterior(secuencia, 0)}>
            <CheckoutSectionCard
              title={checkout.tripHeadline}
              estado={estadoViaje}
              resumen={resumenViaje}
              actionLabel={tarjeta('viaje') === 'completado' ? checkout.changeStep : tarjeta('viaje') === 'editando' ? checkout.doneEditing : undefined}
              onAction={tarjeta('viaje') === 'activo' ? undefined : () => setEditando((e) => (e === 'viaje' ? null : 'viaje'))}
              pie={tarjeta('viaje') === 'activo' ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso> : undefined}
            >
              <BloqueViajePaquete
                lang={lang}
                dict={dict}
                paquete={paquete}
                minDate={minDate}
                inicio={estado.inicio}
                hora={estado.hora}
                moneda={estado.moneda}
                personasPaquete={personasPaquete}
                maxPersonas={maxPersonas}
                slugPrincipal={slugPrincipal}
                noches={noches}
                salida={salida}
                formatearFecha={formatearFecha}
                errorViaje={errorViaje}
                despachar={despachar}
                onTopePersonas={() => ayuda.tropezar('tope-personas')}
              />
            </CheckoutSectionCard>
            </ItemPaso>

            {tarjeta('contacto') !== 'oculto' && (
              <ItemPaso unida={unidaConAnterior(secuencia, 1)}>
              <CheckoutSectionCard
                title={checkout.contactHeadline}
                estado={estadoContacto as 'activo' | 'editando' | 'completado' | 'suspendido'}
                resumen={`${estado.contacto.fullName} · ${estado.contacto.email}`}
                actionLabel={tarjeta('contacto') === 'completado' ? checkout.changeStep : tarjeta('contacto') === 'editando' ? checkout.doneEditing : undefined}
                onAction={tarjeta('contacto') === 'activo' ? undefined : () => setEditando((e) => (e === 'contacto' ? null : 'contacto'))}
                pie={tarjeta('contacto') === 'activo' ? <BotonPaso onClick={confirmarDatos}>{checkout.confirmStep}</BotonPaso> : undefined}
              >
                <BloqueContacto
                  idPrefijo="pedido"
                  checkout={checkout}
                  valores={estado.contacto}
                  errores={erroresContacto}
                  onCambio={(campo, valor) => despachar({ tipo: 'contacto', cambios: { [campo]: valor } })}
                />
              </CheckoutSectionCard>
              </ItemPaso>
            )}

            {tarjeta('detalles') !== 'oculto' && (
              <>
                {paquete.servicios_asociados.map((componente, indice) => {
                  if (indice > gruposCompletados || grupoOculto(indice)) return null;
                  const slug = componente.servicio.slug;
                  const estadoGrupo = estadoVisible(estadoDeGrupo(indice), hayEdicion);
                  return (
                    <ItemPaso key={componente.id} unida={unidaConAnterior(secuencia, posicionDeGrupo.get(indice) ?? 0)}>
                    <GrupoServicio
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
                      error={indice === indiceGrupoEnFoco ? errorDetalles : ''}
                      onAccion={() => setGrupoEditando((a) => a === indice ? null : indice)}
                      onCompletar={() => confirmarGrupo(indice)}
                      onTope={() => ayuda.tropezar('tope-personas')}
                      onPersonas={(valor) => despachar(paquete.precio_depende_de_personas && slugPrincipal
                        ? { tipo: 'personasLogistica', slug, slugPrincipal, valor }
                        : { tipo: 'personas', slug, valor })}
                      onExtras={(valor) => despachar({ tipo: 'extras', slug, valor })}
                      onTraslado={(cambios) => despachar({ tipo: 'traslado', slug, cambios })}
                    />
                    </ItemPaso>
                  );
                })}
                <ErrorDeCampo id="pedido-detalles-error-general" mensaje={indiceGrupoEnFoco === null ? errorDetalles : ''} />
              </>
            )}

            {/* El cuarto paso: "Cómo pagas" se pinta aquí (portal del panel) al llegar a él. */}
            {actual === 'pago' && <div ref={setDestinoTarjetaPago} />}
          </>
        }
        pedido={
          <PanelPedidoPaquete
            lang={lang}
            dict={dict}
            paquete={paquete}
            motor={motor}
            pedido={pedido}
            cargos={cargos}
            cantidadCargos={cantidadCargos}
            nombreEmpresa={nombreEmpresa}
            moneda={estado.moneda}
            formaPago={estado.formaPago}
            conUsd={conUsd}
            descuento={descuento}
            codigoPromocional={codigoPromocional}
            promoEstado={promoEstado}
            promoPorcentaje={promoPorcentaje}
            lineasViaje={lineasViaje}
            destinoTarjetaPago={destinoTarjetaPago}
            total={total}
            ahora={ahora}
            ayudaMensaje={ayudaMensaje}
            waiverAccepted={waiverAccepted}
            errorWaiver={errorWaiver}
            captchaKey={captchaKey}
            actual={actual}
            pago={pago}
            despachar={despachar}
            onWaiverChange={(valor) => { setWaiverAccepted(valor); if (valor) setErrorWaiver(false); }}
            onCodigoPromocionalChange={(valor) => {
              setCodigoPromocional(valor);
              setPromoEstado(valor.trim() ? 'verificando' : 'idle');
              setPromoPorcentaje(null);
              setPromoDescuento(null);
            }}
            onCaptchaToken={(token) => { captcha.current = token; }}
            onSubmit={enviar}
          />
        }
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
