'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { AyudaFlotante } from '@/components/checkout/ayuda-flotante';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { BloqueContacto } from '@/components/checkout/bloques/bloque-contacto';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { ItemPaso } from '@/components/checkout/item-paso';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { AvisoProblema } from '@/components/checkout/aviso-problema';
import { useToast } from '@/components/toast';
import { AsistenteMovil } from '@/components/reserva/asistente-movil';
import { useMovil } from '@/components/reserva/use-movil';
import { usePantallaMovil } from '@/components/reserva/use-pantalla-movil';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { anterior as pantallaAnterior, pantallasDe, primeraDelPaso } from '@/lib/pantallas-checkout';
import { useAyudaContextual } from '@/components/checkout/use-ayuda-contextual';
import { useScrollAlFoco } from '@/components/checkout/use-scroll-al-foco';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import { precargarFormularioPago } from '@/components/checkout/pago/pago-diferido';
import { ApiError, validarCodigoPromocional, type PaqueteCatalogo, type PuntoEncuentro, type TrasladosCatalogo } from '@/lib/api';
import { fechaSalida, nochesDelPaquete } from '@/lib/calendario-paquete';
import { fromLocalISODate } from '@/lib/dates';
import { mensajeDeAyuda, mensajeDeError } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import {
  estadoDeTarjeta, estadoVisible, numeroDePaso, pasoAnterior, unidaConAnterior, type EstadoTarjeta, type EstadoVisible, type PasoId,
  rotuloDePaso,
} from '@/lib/pasos-checkout';
import {
  calcularPedido, maxPersonasPaquete, montoInicial, servicioPrincipalPaquete, trasladoFijoAeropuerto, usdDisponible,
} from '@/lib/pedido-paquete';
import { armarPayloadOrden, armarPayloadReserva, zonaEfectivaDeTraslado } from '@/lib/pedido-payload';
import { leerRef } from '@/lib/ref';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { BloqueViajePaquete } from './bloque-viaje-paquete';
import { useBorrador } from '@/components/checkout/use-borrador';
import { useCorregir } from '@/components/checkout/use-corregir';
import { usePasoUrl } from '@/components/checkout/use-paso-url';
import { destinoDeError } from '@/lib/campo-paso';
import { claveBorrador } from '@/lib/borrador-reserva';
import { pasoDeQuery } from '@/lib/paso-url';
import { GrupoDatos } from './grupo-datos';
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
  /** Origen de «salir» en el primer paso (`lib/origen.ts`), ya con idioma. */
  volverHref: string;
  /** `{ nombre, logo }` por slug, de `content/empresas` (server-only: llega por prop). */
  empresas: Record<string, { nombre: string; logo?: string }>;
  retomarCheckoutId?: string;
};

export function PedidoPaquete({ lang, dict, paquete, sedeSlug, tarifasPorEmpresa, puntosPorEmpresa, minDate, volverHref, empresas, retomarCheckoutId }: Props) {
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
  const movil = useMovil();
  // En móvil «corregir» lleva a la pantalla del campo; el asistente se arma más abajo (necesita el
  // borrador, que necesita el pago, que necesita `corregir`): se le alcanza por una referencia.
  const irAPantallaDelCampo = useRef<(destino: { paso: PasoId; campo: string }) => void>(() => {});
  const corregirEnMovil = useCallback(
    (destino: { paso: PasoId; campo: string }) => irAPantallaDelCampo.current(destino),
    [],
  );
  const corregir = useCorregir(actual, setEditando, movil ? corregirEnMovil : undefined);
  const tarjeta = (id: PasoId) => estadoDeTarjeta(id, actual, editando);
  const ayuda = useAyudaContextual();
  const { mostrar: avisar } = useToast();

  // Al llegar a "Cómo pagas" se pide ya el formulario de tarjeta (y con él Stripe.js):
  // para cuando se crea el pago, el chunk está listo. Solo en el cliente.
  useEffect(() => {
    if (actual === 'pago') precargarFormularioPago().catch(() => {});
  }, [actual]);
  // Viaje reúne la fecha y una tarjeta de extras por servicio: la fecha se confirma
  // primero y luego cada servicio, en orden. Al terminar el último se pasa a «Tus datos».
  const [fechaConfirmada, setFechaConfirmada] = useState(false);
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
  const [errorRecogida, setErrorRecogida] = useState('');
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
  // Quién opera el viaje: una empresa por componente, sin repetir; en cruza-empresa, una por cada una.
  const sellosDelPaquete = [...new Set(paquete.servicios_asociados.map((c) => c.servicio.empresa_slug))]
    .map((slug) => empresas[slug])
    .filter((e): e is { nombre: string; logo?: string } => !!e);
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
  ) : '–';
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
    alErrorDeCampo: (err) => {
      const destino = err instanceof ApiError && err.status === 400 ? destinoDeError(err.detail, 'pedido') : null;
      if (destino) corregir(destino);
    },
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

  // La actividad principal de un paquete que depende de personas se elige en
  // Viaje; si no lleva extras, no necesita una tarjeta de detalles adicional.
  const grupoOculto = (indice: number) => {
    const componente = paquete.servicios_asociados[indice];
    return paquete.precio_depende_de_personas && indice > 0 && componente.servicio.slug === slugPrincipal
      && componente.servicio.personalizaciones.length === 0;
  };

  // Borrador de la pestaña y paso en la URL. Solo se repone un borrador si la URL ya trae
  // `?paso=` (recarga, cambio de idioma, Atrás); una entrada nueva desde el sitio lo descarta.
  const reponerBorrador = useSearchParams().get('paso') !== null;
  const borradorListo = useBorrador({
    clave: claveBorrador('paquete', paquete.slug),
    habilitado: true,
    reponer: reponerBorrador,
    terminado: pago.fase === 'exito',
    estado: { estado, paso: actual, fechaConfirmada, gruposCompletados },
    restaurar: (guardado) => {
      despachar({ tipo: 'restaurar', estado: guardado.estado });
      setActual(pasoDeQuery(guardado.paso) ?? 'viaje');
      setFechaConfirmada(Boolean(guardado.fechaConfirmada));
      setGruposCompletados(Math.max(0, Math.min(Number(guardado.gruposCompletados) || 0, paquete.servicios_asociados.length)));
    },
  });
  const pagoEnCurso = pago.fase !== 'formulario' && pago.fase !== 'resumiendo';

  // Móvil (< 640 px): asistente de una pantalla por vez (fecha, un servicio por pantalla, datos,
  // recogida, cómo pagas). La tarjeta de cada empresa es la pantalla de pago aparte (`PantallaPago`).
  const conRecogida = !trasladoFijo && paquete.servicios_asociados.some((c) => estado.componentes[c.servicio.slug]?.traslado);
  const llaveServicios = paquete.servicios_asociados
    .map((_, indice) => indice).filter((indice) => !grupoOculto(indice)).join(',');
  const pantallas = useMemo(
    () => pantallasDe({
      tipo: 'paquete',
      servicios: llaveServicios ? llaveServicios.split(',').map(Number) : [],
      conTraslado: conRecogida,
      empresas: Math.max(1, cantidadCargos),
    }),
    [llaveServicios, conRecogida, cantidadCargos],
  );
  const pantallaInicial = primeraDelPaso(pantallas, actual);
  const asistente = usePantallaMovil({
    pantallas,
    habilitado: movil && borradorListo && !pagoEnCurso,
    inicial: pantallaInicial,
    minima: null,
    tope: 'como-pagas',
    clave: claveBorrador('paquete', paquete.slug),
  });
  const { irA } = asistente;
  useEffect(() => {
    irAPantallaDelCampo.current = (destino) => irA(
      destino.campo.includes('-error-') ? 'contacto'
        : destino.paso === 'datos' && conRecogida ? 'recogida'
          : primeraDelPaso(pantallas, destino.paso),
    );
  }, [irA, conRecogida, pantallas]);
  // Lo que en escritorio reabre una tarjeta (sin fecha, sin cupo, reintento) en móvil lleva a su pantalla.
  const reabrirPaso = (paso: PasoId) => {
    if (movil) irA(primeraDelPaso(pantallas, paso));
    else setEditando(paso);
  };
  const reabrirGrupo = (indice: number) => {
    if (movil) irA(`servicio-${indice}`);
    else setGrupoEditando(indice);
  };

  usePasoUrl({ actual, editando, setEditando, bloqueado: pagoEnCurso, habilitado: borradorListo && !movil });
  // Una sola flecha: «paso anterior» mientras haya uno y no haya un pago en curso; si no, sale al origen.
  const pasoVisible = editando ?? actual;
  const alPasoAnterior = pagoEnCurso
    ? undefined
    : movil
      ? pantallaAnterior(pantallas, asistente.pantalla.id) !== null ? () => { asistente.retroceder(); } : undefined
      : pasoAnterior(pasoVisible) !== null ? () => setEditando(pasoAnterior(pasoVisible)) : undefined;

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

  const confirmarViaje = (): boolean => {
    if (!estado.inicio) {
      setErrorViaje(traslados.errors.seleccionaFecha);
      ayuda.tropezar('validacion');
      return false;
    }
    setErrorViaje('');
    setEditando(null);
    setFechaConfirmada(true);
    return true;
  };

  /** Dónde recogen a cada servicio con traslado propio (la zona incluida): vive en «Tus datos». */
  const errorDeRecogidas = (): { indice: number; error: string } | null => {
    for (let indice = 0; indice < paquete.servicios_asociados.length; indice++) {
      const error = errorDeGrupo(indice, 'datos');
      if (error) return { indice, error };
    }
    return null;
  };

  const confirmarDatos = (): boolean => {
    const contactoValido = validarDatos();
    const recogida = errorDeRecogidas();
    setErrorRecogida(recogida?.error ?? '');
    if (!contactoValido || recogida) {
      ayuda.tropezar('validacion');
      return false;
    }
    setEditando(null);
    setActual((a) => (a === 'datos' ? 'pago' : a));
    return true;
  };

  const errorDeGrupo = (indice: number, parte?: 'viaje' | 'datos'): string => errorDeGrupoPaquete({
    indice, paquete, componentes: estado.componentes, inicio: estado.inicio, trasladoFijo, noches, zonaDePunto,
    textos, traslados, checkout, parte,
  });

  const confirmarGrupo = (indice: number): boolean => {
    const error = errorDeGrupo(indice, 'viaje');
    if (error) {
      ayuda.tropezar('validacion');
      if (!estado.inicio) {
        setErrorViaje(error);
        setErrorDetalles('');
        reabrirPaso('viaje');
      } else {
        setErrorDetalles(error);
      }
      return false;
    }
    setErrorDetalles('');
    let siguiente = indice + 1;
    while (siguiente < paquete.servicios_asociados.length && grupoOculto(siguiente)) siguiente += 1;
    setGruposCompletados(siguiente);
    if (siguiente >= paquete.servicios_asociados.length) setActual('datos');
    return true;
  };

  const enviar = () => {
    if (actual !== 'pago') return;
    for (let indice = 0; indice < paquete.servicios_asociados.length; indice++) {
      const error = errorDeGrupo(indice, 'viaje');
      if (error) {
        if (!estado.inicio) {
          setErrorViaje(error);
          setErrorDetalles('');
          reabrirPaso('viaje');
        } else {
          setErrorDetalles(error);
          reabrirGrupo(indice);
        }
        return;
      }
    }
    const contactoValido = validarDatos();
    const recogida = errorDeRecogidas();
    setErrorRecogida(recogida?.error ?? '');
    if (!contactoValido || recogida) {
      ayuda.tropezar('validacion');
      const errores = erroresDeContacto(estado.contacto, checkout);
      const primero = (['fullName', 'phone', 'email'] as const).find((campo) => errores[campo]);
      corregir({ paso: 'datos', campo: primero ? `pedido-error-${primero}` : '' });
      return;
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
    if (!llegoAlPago) reabrirPaso('viaje'); // p. ej. ya no hay cupo: se abre la fecha para cambiarla
  };

  // Cruza-empresa: cada cobro es un paso del stepper y su cifra es la de ese
  // cobro (no el total del pedido), para que coincida con el botón de pagar.
  // Con un solo cobro el stepper queda de 3 pasos.
  const stepperPagos = (indicePago: number, monto?: number) => {
    if (cantidadCargos <= 1) return null;
    const dato = monto ?? cargos[indicePago]?.monto;
    return {
      steps: [
        checkout.stepper.viaje, checkout.stepper.datos,
        ...cargos.map((cargo, i) => checkout.stepper.paymentNumbered
          .replace('{n}', String(i + 1)).replace('{empresa}', nombreEmpresa(cargo.empresaSlug))),
      ],
      etiquetasCortas: [
        checkout.stepper.viaje, checkout.stepper.datos,
        ...cargos.map((_, i) => checkout.stepper.paymentShort.replace('{n}', String(i + 1))),
      ],
      actual: numeroDePaso('pago') + indicePago,
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
      stepper={stepperPagos(pago.fallo?.indice ?? 0) ?? { actual: numeroDePaso('pago'), totalMovil }}
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
      paquete={paquete}
      motor={motor}
      moneda={estado.moneda}
      pago={pago}
      cantidadCargos={cantidadCargos}
      nombreEmpresa={nombreEmpresa}
      personasPaquete={personasPaquete}
      stepperPagos={stepperPagos}
      volverHref={volverHref}
      empresa={paquete.es_cruza_empresa ? undefined : empresas[paquete.empresa_lider_slug]}
      sellos={sellosDelPaquete}
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
      sedeSlug={sedeSlug}
      empresas={empresas}
      onOrdenCancelada={(linea) => {
        reiniciarPedido();
        avisar('info', linea);
      }}
    />
  );

  // Un solo foco abierto: si el cliente reabrió una respuesta, la tarjeta activa
  // se pliega a un renglón "pendiente" hasta que termine de corregirla.
  const hayEdicion = editando !== null || grupoEditando !== null;
  const estadoDeGrupo = (indice: number): EstadoTarjeta =>
    indice < gruposCompletados ? (grupoEditando === indice ? 'editando' : 'completado') : 'activo';
  // La fecha es la primera tarjeta de Viaje: «activa» hasta confirmarla (pasar a «Tus datos»
  // o más allá implica que ya está confirmada), «editando» si el cliente la reabre.
  const fechaLista = fechaConfirmada || actual !== 'viaje';
  const estadoFecha: EstadoTarjeta = !fechaLista ? 'activo' : editando === 'viaje' ? 'editando' : 'completado';
  const estadoViaje = estadoVisible(estadoFecha, hayEdicion);
  const estadoDatos: EstadoVisible = estadoVisible(
    (tarjeta('datos') === 'oculto' ? 'activo' : tarjeta('datos')) as EstadoTarjeta, hayEdicion,
  );
  // Orden exacto en el que se pintan las tarjetas, para saber cuáles van pegadas.
  const secuencia: EstadoVisible[] = [estadoViaje];
  const posicionDeGrupo = new Map<number, number>();
  if (fechaLista) {
    paquete.servicios_asociados.forEach((_, indice) => {
      if (indice > gruposCompletados || grupoOculto(indice)) return;
      posicionDeGrupo.set(indice, secuencia.length);
      secuencia.push(estadoVisible(estadoDeGrupo(indice), hayEdicion));
    });
  }
  const posicionDatos = secuencia.length;
  if (tarjeta('datos') !== 'oculto') secuencia.push(estadoDatos);

  // El error de detalles vive en la tarjeta de grupo que está en foco (la que lo
  // causó, pegado a su CTA); si no hay ninguna en foco, va debajo de la lista.
  const indiceGrupoEnFoco = [...posicionDeGrupo.entries()]
    .find(([, posicion]) => secuencia[posicion] === 'activo' || secuencia[posicion] === 'editando')?.[0] ?? null;

  // Los mismos bloques en las tarjetas de escritorio y en las pantallas del asistente móvil.
  const bloqueViaje = (
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
  );
  const grupoServicio = (
    componente: (typeof paquete.servicios_asociados)[number],
    indice: number,
    estadoTarjeta: 'activo' | 'editando' | 'completado' | 'suspendido',
    error: string,
  ) => {
    const slug = componente.servicio.slug;
    return (
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
        logoEmpresa={empresas[componente.servicio.empresa_slug]?.logo}
        moneda={estado.moneda}
        tipoCambio={paquete.tipo_cambio_usd}
        inicio={estado.inicio}
        noches={noches}
        salida={salida}
        estadoTarjeta={estadoTarjeta}
        error={error}
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
  };
  const bloqueContacto = (
    <BloqueContacto
      idPrefijo="pedido"
      checkout={checkout}
      valores={estado.contacto}
      errores={erroresContacto}
      onCambio={(campo, valor) => despachar({ tipo: 'contacto', cambios: { [campo]: valor } })}
    />
  );
  // La pregunta «¿Dónde te recogemos?» va como título: el de la tarjeta de datos o el de la pantalla.
  const recogidas = (conTitulo: boolean) => (
    <>
      {paquete.servicios_asociados.map((componente) => {
        const slug = componente.servicio.slug;
        const traslado = estado.componentes[slug]?.traslado;
        if (!traslado || trasladoFijo) return null;
        return (
          <div key={componente.id} className="flex flex-col border-t border-borde pt-5">
            {conTitulo && <p className="texto-etiqueta text-foreground">{traslados.fields.dondeRecogemos}</p>}
            <p className={`${conTitulo ? 'mt-1 ' : ''}texto-pequeno text-apagado`}>{traslados.fields.recogidaAyuda}</p>
            {cantidadCargos > 1 && (
              <p className="mt-1 texto-pequeno text-apagado">
                {`${componente.servicio.nombre} · ${nombreEmpresa(componente.servicio.empresa_slug)}`}
              </p>
            )}
            <GrupoDatos
              traslados={traslados}
              traslado={traslado}
              servicioSlug={slug}
              puntos={puntosPorEmpresa[componente.servicio.empresa_slug] ?? []}
              onTraslado={(cambios) => despachar({ tipo: 'traslado', slug, cambios })}
            />
          </div>
        );
      })}
      <ErrorDeCampo id="pedido-recogida-error" mensaje={errorRecogida} />
    </>
  );

  // Móvil: una pantalla por vez. Cada pantalla trae su «Continuar»; «Cómo pagas» manda a la barra
  // el botón de su tarjeta por portal.
  const pantalla = asistente.pantalla;
  const continuar = checkout.barra.continuar;
  const pantallaMovil = (() => {
    switch (pantalla.tipo) {
      case 'inicio':
        return { titulo: checkout.tripHeadline, contenido: bloqueViaje, accion: {
          etiqueta: continuar,
          alPulsar: () => { if (confirmarViaje()) asistente.avanzar(); },
        } };
      case 'servicio': {
        const componente = paquete.servicios_asociados[pantalla.indice];
        return {
          titulo: componente.servicio.nombre,
          antetitulo: cantidadCargos > 1 ? (
            <EmpresaSello
              nombre={nombreEmpresa(componente.servicio.empresa_slug)}
              logo={empresas[componente.servicio.empresa_slug]?.logo}
              tamano={24}
              mostrarNombre
            />
          ) : undefined,
          contenido: grupoServicio(componente, pantalla.indice, 'activo', errorDetalles),
          accion: {
            etiqueta: continuar,
            alPulsar: () => { if (confirmarGrupo(pantalla.indice)) asistente.avanzar(); },
          },
        };
      }
      case 'contacto':
        return { titulo: checkout.stepper.datos, contenido: bloqueContacto, accion: {
          etiqueta: continuar,
          alPulsar: () => {
            // Con recogida, el contacto se valida aquí y la recogida en su pantalla.
            if (conRecogida ? validarDatos() : confirmarDatos()) asistente.avanzar();
            else if (conRecogida) ayuda.tropezar('validacion');
          },
        } };
      case 'recogida':
        return { titulo: traslados.fields.dondeRecogemos, contenido: <div className="flex flex-col gap-6">{recogidas(false)}</div>, accion: {
          etiqueta: continuar,
          alPulsar: () => { if (confirmarDatos()) asistente.avanzar(); },
        } };
      default:
        // Sin precio en Pago el catálogo no responde: la pantalla es el aviso, sin botón que no sirve.
        return { titulo: checkout.howYouPay, contenido: pedido
          ? <div ref={setDestinoTarjetaPago} />
          : <AvisoProblema checkout={checkout} feedback={feedback} tipo="catalogo_caido" ayudaMensaje={ayudaMensaje} /> };
    }
  })();
  const asistenteMovil = (
    <AsistenteMovil
      id={pantalla.id}
      titulo={pantallaMovil.titulo}
      antetitulo={'antetitulo' in pantallaMovil ? pantallaMovil.antetitulo : undefined}
      soloFundido={pantalla.paso === 'pago'}
      anuncio={`${rotuloDePaso(checkout.stepper.stepOf, pantalla.paso)}: ${checkout.stepper[pantalla.paso]}`}
      accion={'accion' in pantallaMovil ? pantallaMovil.accion : undefined}
    >
      {pantallaMovil.contenido}
    </AsistenteMovil>
  );

  return (
    <>
      <PaginaCheckout
        lang={lang}
        dict={dict}
        volverHref={volverHref}
        alPasoAnterior={alPasoAnterior}
        empresa={paquete.es_cruza_empresa ? undefined : empresas[paquete.empresa_lider_slug]}
        volverLabel={textos.back}
        encabezado={
          <EncabezadoCompra
            titulo={checkout.tituloPagina.paquete}
            detalle={[paquete.nombre, detalleCompra].filter(Boolean).join(' · ')}
          />
        }
        stepper={(!movil && actual === 'pago' ? stepperPagos(0) : null) ?? {
          actual: numeroDePaso(movil ? asistente.pantalla.paso : actual), totalMovil,
          steps: cantidadCargos > 1 ? stepperPagos(0)?.steps : undefined,
          etiquetasCortas: cantidadCargos > 1 ? stepperPagos(0)?.etiquetasCortas : undefined,
        }}
        pasos={movil ? asistenteMovil : (
          <>
            <ItemPaso unida={unidaConAnterior(secuencia, 0)}>
            <CheckoutSectionCard
              title={checkout.tripHeadline}
              pasoRotulo={rotuloDePaso(checkout.stepper.stepOf, 'viaje')}
              estado={estadoViaje}
              resumen={resumenViaje}
              actionLabel={estadoFecha === 'completado' ? checkout.changeStep : estadoFecha === 'editando' ? checkout.doneEditing : undefined}
              onAction={estadoFecha === 'activo' ? undefined : () => setEditando((e) => (e === 'viaje' ? null : 'viaje'))}
              pie={estadoFecha === 'activo' ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso> : undefined}
            >
              {bloqueViaje}
            </CheckoutSectionCard>
            </ItemPaso>

            {fechaLista && (
              <>
                {paquete.servicios_asociados.map((componente, indice) => {
                  if (indice > gruposCompletados || grupoOculto(indice)) return null;
                  const estadoGrupo = estadoVisible(estadoDeGrupo(indice), hayEdicion);
                  return (
                    <ItemPaso key={componente.id} unida={unidaConAnterior(secuencia, posicionDeGrupo.get(indice) ?? 0)}>
                    {grupoServicio(componente, indice, estadoGrupo, indice === indiceGrupoEnFoco ? errorDetalles : '')}
                    </ItemPaso>
                  );
                })}
                <ErrorDeCampo id="pedido-detalles-error-general" mensaje={indiceGrupoEnFoco === null ? errorDetalles : ''} />
              </>
            )}

            {tarjeta('datos') !== 'oculto' && (
              <ItemPaso unida={unidaConAnterior(secuencia, posicionDatos)}>
              <CheckoutSectionCard
                title={checkout.stepper.datos}
                pasoRotulo={rotuloDePaso(checkout.stepper.stepOf, 'datos')}
                estado={estadoDatos as 'activo' | 'editando' | 'completado' | 'suspendido'}
                resumen={`${estado.contacto.fullName} · ${estado.contacto.email}`}
                actionLabel={tarjeta('datos') === 'completado' ? checkout.changeStep : tarjeta('datos') === 'editando' ? checkout.doneEditing : undefined}
                onAction={tarjeta('datos') === 'activo' ? undefined : () => setEditando((e) => (e === 'datos' ? null : 'datos'))}
                pie={tarjeta('datos') === 'activo' ? <BotonPaso conFlecha onClick={confirmarDatos}>{checkout.continueToPayment || checkout.confirmStep}</BotonPaso> : undefined}
              >
                <div className="flex flex-col gap-6">
                  {bloqueContacto}
                  {recogidas(true)}
                </div>
              </CheckoutSectionCard>
              </ItemPaso>
            )}

            {/* El cuarto paso: "Cómo pagas" se pinta aquí (portal del panel) al llegar a él. */}
            {actual === 'pago' && <div ref={setDestinoTarjetaPago} />}
          </>
        )}
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
            sellos={sellosDelPaquete}
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
            onElegirFecha={() => reabrirPaso('viaje')}
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
