'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BookingConfirmation } from '@/components/booking-confirmation';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { precargarFormularioPago } from '@/components/checkout/pago/pago-diferido';
import { AyudaFlotante } from '@/components/checkout/ayuda-flotante';
import { BloqueContacto } from '@/components/checkout/bloques/bloque-contacto';
import { BloquePago, BloqueTarjetaPago } from '@/components/checkout/bloques/bloque-pago';
import { BloqueRecogida } from '@/components/checkout/bloques/bloque-recogida';
import { BloqueViajeTraslado } from '@/components/checkout/bloques/bloque-viaje-traslado';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { formatDay } from '@/components/checkout/formato-dia';
import { ItemPaso } from '@/components/checkout/item-paso';
import { ReservaPlegable } from '@/components/pedido/reserva-plegable';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { useAyudaContextual } from '@/components/checkout/use-ayuda-contextual';
import { useScrollAlFoco } from '@/components/checkout/use-scroll-al-foco';
import { useToast } from '@/components/toast';
import {
  ApiError,
  crearPago,
  crearReservaTraslado,
  getEstadoReserva,
  validarCodigoPromocional,
  type Moneda,
  type Pago,
  type ReservaTrasladoInput,
  type TipoTraslado,
  type TrasladosCatalogo,
  type Zona,
} from '@/lib/api';
import {
  formatHour,
  fromLocalISODate,
  generarHorasVentana,
  getMinBookableDate,
  toLocalISODate,
} from '@/lib/dates';
import { mensajeDeFallo } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import {
  estadoDeTarjeta, estadoVisible, numeroDePaso, unidaConAnterior, type EstadoTarjeta, type EstadoVisible, type PasoId,
} from '@/lib/pasos-checkout';
import { leerRef } from '@/lib/ref';
import { borrarPendiente, guardarPendiente } from '@/lib/pendientes';

const CLAVE_CHECKOUT_ID = 'salysol:traslados:checkout_id';
const DIGITOS_TELEFONO_MIN = 8;
const DIGITOS_TELEFONO_MAX = 15;

function telefonoValido(valor: string) {
  if (!/^[\d\s+()\-.]+$/.test(valor.trim())) return false;
  const digitos = valor.replace(/\D/g, '').length;
  return digitos >= DIGITOS_TELEFONO_MIN && digitos <= DIGITOS_TELEFONO_MAX;
}

function nombreValido(valor: string) {
  return !/\d/.test(valor) && /\p{L}/u.test(valor);
}

function correoValido(valor: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor.trim());
}

function diaSiguiente(iso: string): string {
  const d = fromLocalISODate(iso);
  d.setDate(d.getDate() + 1);
  return toLocalISODate(d);
}

type CampoContacto = 'phone' | 'fullName' | 'email';
const ORDEN_CAMPOS: CampoContacto[] = ['phone', 'fullName', 'email'];

type Phase = 'recuperando' | 'form' | 'submitting' | 'payment' | 'confirmed' | 'unavailable' | 'error';
type TrasladoViewProps = {
  lang: Locale;
  dict: Dictionary;
  catalogo: TrasladosCatalogo;
  empresaSlug: string;
  sedeSlugActual?: string;
};

export function TrasladoView({
  lang,
  dict,
  catalogo,
  empresaSlug,
  sedeSlugActual,
}: TrasladoViewProps) {
  const { checkout, traslados, feedback, booking, pedido } = dict;
  const { mostrar } = useToast();

  const [checkoutId, setCheckoutId] = useState('');
  const [recuperable, setRecuperable] = useState(false);
  const [phase, setPhase] = useState<Phase>('recuperando');
  /* eslint-disable react-hooks/set-state-in-effect -- lectura unica de sessionStorage en cliente */
  useLayoutEffect(() => {
    const guardado = window.sessionStorage.getItem(CLAVE_CHECKOUT_ID);
    if (guardado) {
      setCheckoutId(guardado);
      setRecuperable(true);
    } else {
      const nuevo = crypto.randomUUID();
      window.sessionStorage.setItem(CLAVE_CHECKOUT_ID, nuevo);
      setCheckoutId(nuevo);
      setPhase('form');
    }
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Viaje (tipo, fechas, hora y pasajeros) → Datos → Recogida → Pago: la misma
  // secuencia que el resto de los checkouts. `editando` es la respuesta ya dada
  // que el cliente reabrió con "Modificar".
  const [actual, setActual] = useState<PasoId>('viaje');
  const [editando, setEditando] = useState<PasoId | null>(null);
  const ayuda = useAyudaContextual();

  // Al llegar a "Cómo pagas" se pide ya el formulario de tarjeta (y con él Stripe.js):
  // para cuando se crea el pago, el chunk está listo. Solo en el cliente.
  useEffect(() => {
    if (actual === 'pago') precargarFormularioPago().catch(() => {});
  }, [actual]);

  const [tipoTraslado, setTipoTraslado] = useState<TipoTraslado>('redondo_aeropuerto');

  const [modoHospedaje, setModoHospedaje] = useState<'catalogo' | 'personalizada'>('catalogo');
  const [puntoEncuentroId, setPuntoEncuentroId] = useState<number | null>(() => {
    return catalogo.puntos_encuentro[0]?.id ?? null;
  });
  const [direccionPersonalizada, setDireccionPersonalizada] = useState('');
  const [zonaPersonalizada, setZonaPersonalizada] = useState<Zona | ''>('');
  // Error de la tarjeta de recogida (hotel o dirección).
  const [errorPaso2, setErrorPaso2] = useState('');

  const minDate = useMemo(() => getMinBookableDate(), []);
  const [fecha, setFecha] = useState(minDate);
  const [fechaRegreso, setFechaRegreso] = useState<string | null>(() => diaSiguiente(minDate));
  const horasDisponibles = useMemo(() => {
    return generarHorasVentana(
      catalogo.servicio.hora_apertura,
      catalogo.servicio.hora_cierre,
      catalogo.servicio.paso_hora_minutos,
    );
  }, [catalogo.servicio.hora_apertura, catalogo.servicio.hora_cierre, catalogo.servicio.paso_hora_minutos]);
  const [hora, setHora] = useState(horasDisponibles[0] ?? '');
  // Error de la tarjeta de viaje (fechas).
  const [errorPaso3, setErrorPaso3] = useState('');

  const maxCapacidad = catalogo.servicio.capacidad_maxima ?? 14;
  const [personas, setPersonas] = useState(2);

  const [contact, setContact] = useState({ phone: '', fullName: '', email: '' });
  const [erroresContacto, setErroresContacto] = useState<Partial<Record<CampoContacto, string>>>({});
  const refPhone = useRef<HTMLInputElement>(null);
  const refFullName = useRef<HTMLInputElement>(null);
  const refEmail = useRef<HTMLInputElement>(null);
  const refsContacto: Record<CampoContacto, React.RefObject<HTMLInputElement | null>> = {
    phone: refPhone,
    fullName: refFullName,
    email: refEmail,
  };
  // Al cambiar de paso, la tarjeta en foco se trae a la vista solo si hace falta.
  useScrollAlFoco(`${actual}|${editando}|${phase === 'payment'}`);

  const [moneda, setMoneda] = useState<Moneda>('MXN');
  const usdDisponible = Number(catalogo.servicio.tipo_cambio_usd) > 0;

  const permiteAnticipo = catalogo.servicio.permite_anticipo;
  const [formaPagoSeleccionada, setFormaPagoSeleccionada] = useState<'completo' | 'anticipo'>('completo');
  const formaPago = permiteAnticipo ? formaPagoSeleccionada : 'completo';
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [errorWaiver, setErrorWaiver] = useState(false);
  const captchaToken = useRef('');

  const [codigoPromocional, setCodigoPromocional] = useState('');
  const [promoEstado, setPromoEstado] = useState<'idle' | 'verificando' | 'valido' | 'invalido'>('idle');
  const [promoPorcentaje, setPromoPorcentaje] = useState<string | null>(null);
  // Lo que resta el codigo segun el servidor (misma funcion que `crear-pago`).
  const [promoDescuento, setPromoDescuento] = useState<{ valor: number; base: number | null } | null>(null);

  const [reservaId, setReservaId] = useState<number | null>(null);
  const [pago, setPago] = useState<Pago | null>(null);
  // Donde se pinta la tarjeta "Cómo pagas" (el último paso, en la columna de pasos).
  const [destinoTarjetaPago, setDestinoTarjetaPago] = useState<HTMLElement | null>(null);
  const [pagoProcesando, setPagoProcesando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!checkoutId || !recuperable) return;
    let activo = true;
    getEstadoReserva(checkoutId, empresaSlug).then((estado) => {
      if (!activo) return;
      if (estado.estado === 'cancelada') {
        const nuevo = crypto.randomUUID();
        window.sessionStorage.setItem(CLAVE_CHECKOUT_ID, nuevo);
        setCheckoutId(nuevo);
        setRecuperable(false);
        setPhase('form');
        return;
      }
      setReservaId(estado.reserva_id);
      setFecha(estado.fecha);
      setHora(estado.hora);
      setPersonas(estado.numero_personas);
      setContact({ phone: 'telefono_cliente' in estado ? estado.telefono_cliente : '',
        fullName: estado.nombre_cliente, email: estado.correo_cliente });
      setMoneda(estado.moneda);
      if (estado.forma_pago === 'anticipo' || estado.forma_pago === 'completo') {
        setFormaPagoSeleccionada(estado.forma_pago);
      }
      if (estado.estado === 'pagada') {
        setPhase('confirmed');
        return;
      }
      const detalle = estado.detalle_transporte;
      if (detalle) {
        setTipoTraslado(detalle.tipo_traslado);
        setModoHospedaje(detalle.punto_encuentro_id === null ? 'personalizada' : 'catalogo');
        setPuntoEncuentroId(detalle.punto_encuentro_id);
        setDireccionPersonalizada(detalle.direccion_personalizada);
        setZonaPersonalizada(detalle.zona);
        setFechaRegreso(detalle.fecha_regreso);
        setPersonas(detalle.numero_personas ?? estado.numero_personas);
      }
      setActual('pago');
      setPhase('form');
    }).catch(() => {
      if (activo) setPhase('form');
    });
    return () => { activo = false; };
  }, [checkoutId, empresaSlug, recuperable]);

  useEffect(() => {
    if (phase === 'confirmed' && checkoutId) borrarPendiente(checkoutId);
  }, [phase, checkoutId]);

  const zonaEfectiva = useMemo<Zona | ''>(() => {
    if (tipoTraslado !== 'redondo_actividad') return '';
    if (modoHospedaje === 'catalogo' && puntoEncuentroId !== null) {
      const punto = catalogo.puntos_encuentro.find((p) => p.id === puntoEncuentroId);
      return punto?.zona ?? '';
    }
    return zonaPersonalizada;
  }, [tipoTraslado, modoHospedaje, puntoEncuentroId, zonaPersonalizada, catalogo.puntos_encuentro]);

  const tarifaAplicable = useMemo(() => {
    return catalogo.tarifas.find((t) => {
      if (t.tipo_traslado !== tipoTraslado) return false;
      if (tipoTraslado === 'redondo_actividad' && t.zona !== zonaEfectiva) return false;
      if (personas < t.personas_min) return false;
      if (t.personas_max !== null && personas > t.personas_max) return false;
      return true;
    });
  }, [catalogo.tarifas, tipoTraslado, zonaEfectiva, personas]);

  const precioBase = useMemo(() => {
    if (!tarifaAplicable) return null;
    return aMoneda(tarifaAplicable.precio, moneda, catalogo.servicio.tipo_cambio_usd);
  }, [tarifaAplicable, moneda, catalogo.servicio.tipo_cambio_usd]);

  const descuento = useMemo(() => {
    if (promoEstado === 'valido' && promoPorcentaje && precioBase !== null) {
      return Math.min(precioBase, promoDescuento && promoDescuento.base === precioBase ? promoDescuento.valor : (precioBase * parseFloat(promoPorcentaje)) / 100);
    }
    return 0;
  }, [promoEstado, promoPorcentaje, promoDescuento, precioBase]);

  const total = precioBase !== null ? Math.max(0, precioBase - descuento) : null;
  const amountDueNow = total === null
    ? null
    : formaPago === 'anticipo'
      ? Math.round(total * (catalogo.servicio.porcentaje_anticipo / 100) * 100) / 100
      : total;

  const currency = useMemo(
    () =>
      new Intl.NumberFormat(intlLocale(lang), {
        style: 'currency',
        currency: moneda,
        currencyDisplay: 'narrowSymbol',
        minimumFractionDigits: 2,
      }),
    [lang, moneda],
  );
  const lines = useMemo(() => {
    if (precioBase === null) return [];
    const tipoTitulo = traslados.types[tipoTraslado]?.title ?? tipoTraslado;
    const resultado = [
      {
        label: tipoTitulo,
        amount: currency.format(precioBase),
        detail: `${personas} ${traslados.fields.pasajeros.toLowerCase()}`,
      },
    ];
    if (descuento > 0) {
      resultado.push({
        label: checkout.promoCode.valid.replace('{percent}', String(Number(promoPorcentaje))),
        amount: `-${currency.format(descuento)}`,
        detail: codigoPromocional.toUpperCase(),
      });
    }
    return resultado;
  }, [precioBase, descuento, tipoTraslado, personas, traslados, checkout, promoPorcentaje, codigoPromocional, currency]);

  const validarContacto = (): Partial<Record<CampoContacto, string>> => {
    const errs: Partial<Record<CampoContacto, string>> = {};
    if (!contact.fullName.trim()) errs.fullName = checkout.missingFields;
    else if (!nombreValido(contact.fullName)) errs.fullName = checkout.invalidName;

    if (!contact.phone.trim()) errs.phone = checkout.missingFields;
    else if (!telefonoValido(contact.phone)) errs.phone = checkout.invalidPhone;

    if (!contact.email.trim()) errs.email = checkout.missingFields;
    else if (!correoValido(contact.email)) errs.email = checkout.invalidEmail;

    return errs;
  };

  /** Lo que falta o está mal en las fechas del viaje; vacío = todo bien. */
  const errorDeViaje = (): string => {
    if (!fecha) return traslados.errors.seleccionaFecha;
    if (tipoTraslado === 'redondo_aeropuerto') {
      if (!fechaRegreso) return traslados.errors.seleccionaFechaRegreso;
      if (fechaRegreso <= fecha) return traslados.errors.fechaRegresoPosterior;
    }
    return '';
  };

  /** Lo que falta o está mal en la recogida (hotel o dirección); vacío = todo bien. */
  const errorDeRecogida = (): string => {
    if (modoHospedaje === 'catalogo') {
      return puntoEncuentroId === null ? traslados.errors.seleccionaHospedaje : '';
    }
    if (!direccionPersonalizada.trim()) return traslados.errors.seleccionaHospedaje;
    if (tipoTraslado === 'redondo_actividad' && !zonaPersonalizada) return traslados.errors.seleccionaZona;
    return '';
  };

  const confirmarViaje = () => {
    const falla = errorDeViaje();
    setErrorPaso3(falla);
    if (falla) {
      ayuda.tropezar('validacion');
      return;
    }
    setActual((a) => (a === 'viaje' ? 'datos' : a));
    setEditando(null);
  };

  /** «Tus datos» junta contacto y recogida: se validan juntos antes de pasar al pago. */
  const confirmarDatos = () => {
    const errs = validarContacto();
    setErroresContacto(errs);
    const falla = errorDeRecogida();
    setErrorPaso2(falla);
    if (Object.keys(errs).length > 0) {
      ayuda.tropezar('validacion');
      const primero = ORDEN_CAMPOS.find((c) => errs[c]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }
    if (falla) {
      ayuda.tropezar('validacion');
      return;
    }
    setActual((a) => (a === 'datos' ? 'pago' : a));
    setEditando(null);
  };

  const onCodigoPromocionalChange = (codigo: string) => {
    setCodigoPromocional(codigo);
    if (!codigo.trim()) {
      setPromoEstado('idle');
      setPromoPorcentaje(null);
      setPromoDescuento(null);
      return;
    }
    setPromoEstado('verificando');
    validarCodigoPromocional(codigo, contact.email, empresaSlug, precioBase)
      .then((res) => {
        if (res.valido && res.porcentaje_descuento) {
          setPromoEstado('valido');
          setPromoPorcentaje(res.porcentaje_descuento);
          setPromoDescuento(res.descuento === null ? null : { valor: Number(res.descuento), base: precioBase });
        } else {
          setPromoEstado('invalido');
          setPromoPorcentaje(null);
          setPromoDescuento(null);
        }
      })
      .catch(() => {
        setPromoEstado('invalido');
        setPromoPorcentaje(null);
        setPromoDescuento(null);
      });
  };

  const iniciarPago = async () => {
    // Lo ya confirmado se revalida: cambiar el tipo de traslado después de elegir
    // la recogida puede dejarla incompleta (p. ej. ahora pide zona).
    const fallaViaje = errorDeViaje();
    if (fallaViaje) {
      setErrorPaso3(fallaViaje);
      setEditando('viaje');
      ayuda.tropezar('validacion');
      return;
    }
    const errs = validarContacto();
    setErroresContacto(errs);
    if (Object.keys(errs).length > 0) {
      setEditando('datos');
      ayuda.tropezar('validacion');
      const primero = ORDEN_CAMPOS.find((c) => errs[c]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }
    const fallaRecogida = errorDeRecogida();
    if (fallaRecogida) {
      setErrorPaso2(fallaRecogida);
      setEditando('datos');
      ayuda.tropezar('validacion');
      return;
    }
    if (!waiverAccepted) {
      ayuda.tropezar('validacion');
      setErrorWaiver(true);
      return;
    }
    if (phase === 'submitting' || phase === 'payment') return;

    setPhase('submitting');
    setError('');

    try {
      const payload: ReservaTrasladoInput = {
        checkout_id: checkoutId,
        servicio: catalogo.servicio.slug,
        tipo_traslado: tipoTraslado,
        punto_encuentro: modoHospedaje === 'catalogo' ? puntoEncuentroId : undefined,
        direccion_personalizada: modoHospedaje === 'personalizada' ? direccionPersonalizada.trim() : '',
        zona:
          modoHospedaje === 'personalizada' && tipoTraslado === 'redondo_actividad'
            ? (zonaPersonalizada as Zona)
            : undefined,
        fecha,
        hora,
        fecha_regreso: tipoTraslado === 'redondo_aeropuerto' ? fechaRegreso : null,
        numero_personas: personas,
        nombre_cliente: contact.fullName.trim(),
        telefono_cliente: contact.phone.trim(),
        correo_cliente: contact.email.trim(),
        moneda,
        deslinde_aceptado: waiverAccepted,
        deslinde_nombre: contact.fullName.trim(),
        forma_pago: formaPago,
        ref: leerRef(),
        captcha_token: captchaToken.current || undefined,
      };

      const reserva = await crearReservaTraslado(empresaSlug, payload);
      setReservaId(reserva.id);
      guardarPendiente({
        tipo: 'reserva', checkoutId, empresaSlug,
        productoSlug: catalogo.servicio.slug,
        productoNombre: catalogo.servicio.nombre,
        ruta: window.location.pathname + window.location.search,
        actualizadoEn: new Date().toISOString(),
      });

      const pagoResponse = await crearPago(
        reserva.id,
        {
          checkout_id: checkoutId,
          forma_pago: formaPago,
          codigo_promocional:
            promoEstado === 'valido' ? codigoPromocional.trim().toUpperCase() : undefined,
        },
        empresaSlug,
      );

      setPago(pagoResponse);
      setPhase('payment');
      mostrar('exito', feedback.saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setPhase('unavailable');
        return;
      }
      if (err instanceof ApiError && err.status === 400 && promoEstado === 'valido') {
        setPromoEstado('invalido');
        setError(checkout.promoCode.invalid);
        setPhase('error');
        return;
      }
      setError(
        err instanceof ApiError && err.status === 502
          ? checkout.errorPaymentProvider
          : err instanceof ApiError && err.status === 409
            ? checkout.errorPaymentInProgress
            : mensajeDeFallo(err, feedback.error),
      );
      setPhase('error');
    }
  };

  const puntoSeleccionado = catalogo.puntos_encuentro.find((p) => p.id === puntoEncuentroId);
  const resumenRecogida =
    modoHospedaje === 'catalogo'
      ? (puntoSeleccionado?.nombre ?? '')
      : `${direccionPersonalizada}${zonaPersonalizada ? ` (${zonaPersonalizada})` : ''}`;
  const resumenViaje = [
    traslados.types[tipoTraslado]?.title ?? tipoTraslado,
    formatDay(fromLocalISODate(fecha), lang),
    formatHour(hora),
    `${personas} ${traslados.fields.pasajeros.toLowerCase()}`,
  ].join(' · ');
  const resumenDatos = `${contact.fullName} · ${contact.phone}`;

  const locked = phase === 'submitting' || phase === 'payment' || phase === 'unavailable';

  if (phase === 'recuperando') return null;

  if (phase === 'confirmed') {
    return (
      <BookingConfirmation
        lang={lang}
        dict={dict}
        numeroDeConfirmacion={reservaId!}
        nombre={contact.fullName}
        email={contact.email}
        fecha={formatDay(fromLocalISODate(fecha), lang)}
        hora={formatHour(hora)}
        personas={personas}
        extras={[]}
        pagado={total !== null ? currency.format(total) : '–'}
        saldoEnEfectivo={null}
        procesando={pagoProcesando}
      />
    );
  }

  const tiposDisponibles: TipoTraslado[] = [
    'redondo_aeropuerto',
    'redondo_actividad',
    'recepcion_aeropuerto',
  ];

  const getPrecioDesde = (tipo: TipoTraslado) => {
    const tarifasTipo = catalogo.tarifas.filter((t) => t.tipo_traslado === tipo);
    if (tarifasTipo.length === 0) return null;
    const precios = tarifasTipo.map((t) => aMoneda(t.precio, moneda, catalogo.servicio.tipo_cambio_usd));
    if (precios.some((p) => p === null)) return null;
    const min = Math.min(...precios as number[]);
    return currency.format(min);
  };

  const hrefVolver = sedeSlugActual ? `/${lang}/sede/${sedeSlugActual}` : `/${lang}`;

  // --- estados de las tarjetas (un solo foco abierto) -----------------------------------
  const hayEdicion = editando !== null;
  const estadoPaso = (id: PasoId): EstadoTarjeta | 'oculto' => estadoDeTarjeta(id, actual, editando);
  const crudoViaje = estadoPaso('viaje') as EstadoTarjeta;
  const crudoDatos = estadoPaso('datos');
  const estadoViaje = estadoVisible(crudoViaje, hayEdicion);
  const estadoDatos = crudoDatos === 'oculto' ? null : estadoVisible(crudoDatos, hayEdicion);
  const secuencia: EstadoVisible[] = [estadoViaje];
  if (estadoDatos) secuencia.push(estadoDatos);
  const reabrir = (id: PasoId) => setEditando((e) => (e === id ? null : id));
  const etiquetaAccion = (estado: EstadoTarjeta | 'oculto') =>
    estado === 'completado' ? checkout.changeStep : estado === 'editando' ? checkout.doneEditing : undefined;

  const pasoActualStepper = phase === 'submitting' || phase === 'payment' ? numeroDePaso('pago') : numeroDePaso(actual);
  const stepsList = [checkout.stepper.viaje, checkout.stepper.datos, checkout.stepper.pago];
  const totalMovil = total !== null ? `${currency.format(total)} ${moneda}` : undefined;
  // Con anticipo, la cifra del paso de pago es lo que se cobra hoy, no el total.
  const stepperPago = phase === 'payment' && pago && Number(pago.monto_a_cobrar) < Number(pago.precio_total)
    ? {
        actual: pasoActualStepper,
        totalMovil: `${currency.format(Number(pago.monto_a_cobrar))} ${moneda}`,
        rotulo: checkout.stepper.payNow,
        totalGeneral: `${currency.format(Number(pago.precio_total))} ${moneda}`,
      }
    : { actual: pasoActualStepper, totalMovil };

  const recogidaElegida = actual === 'pago' || phase !== 'form';
  const lineasViaje = [
    { etiqueta: traslados.step1Title, valor: traslados.types[tipoTraslado]?.title ?? tipoTraslado },
    { etiqueta: checkout.summary.date, valor: formatDay(fromLocalISODate(fecha), lang) },
    tipoTraslado === 'redondo_aeropuerto' && fechaRegreso
      ? { etiqueta: traslados.fields.fechaRegreso, valor: formatDay(fromLocalISODate(fechaRegreso), lang) }
      : null,
    { etiqueta: checkout.summary.time, valor: formatHour(hora) },
    { etiqueta: checkout.summary.people, valor: String(personas) },
    recogidaElegida && resumenRecogida
      ? { etiqueta: traslados.fields.puntoEncuentro, valor: resumenRecogida }
      : null,
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);
  // Al abrir los renglones de "Tu reserva": viaje sin la recogida (que tiene su propio renglón) y datos de contacto.
  const detalleViaje = lineasViaje.filter((linea) => linea.etiqueta !== traslados.fields.puntoEncuentro);
  const detalleContacto = [
    { etiqueta: checkout.fullName, valor: contact.fullName },
    { etiqueta: checkout.email, valor: contact.email },
    { etiqueta: checkout.phone, valor: contact.phone },
  ].filter((linea) => linea.valor.trim() !== '');
  const detalleRecogida = resumenRecogida
    ? [{ etiqueta: traslados.fields.puntoEncuentro, valor: resumenRecogida }]
    : undefined;

  const ayudaMensaje = `Hola, necesito ayuda con mi reserva de traslado ${tipoTraslado} para ${personas} personas el ${fecha}.`;

  return (
    <>
      <PaginaCheckout
        lang={lang}
        dict={dict}
        sedeSlug={sedeSlugActual}
        volverHref={hrefVolver}
        volverLabel={traslados.back}
        encabezado={
          <EncabezadoCompra
            nombre={traslados.title}
            detalle={traslados.subtitle}
          />
        }
        stepper={{ ...stepperPago, steps: stepsList }}
        pasos={
          <>
            <ReservaPlegable
              activo={phase === 'payment'}
              titulo={dict.pedido.yourBooking}
              etiquetaEstado={dict.pedido.bookingSaved}
              resumen={resumenViaje}
              notaBloqueada={dict.pedido.lockedNote}
              ctaAyuda={dict.pedido.lockedCta}
              mensajeAyuda={ayudaMensaje}
            >
            <ItemPaso unida={unidaConAnterior(secuencia, 0)}>
              <CheckoutSectionCard
                title={checkout.tripHeadline}
                estado={estadoViaje}
                resumen={resumenViaje}
                detalle={detalleViaje}
                actionLabel={locked ? undefined : etiquetaAccion(crudoViaje)}
                onAction={locked || crudoViaje === 'activo' ? undefined : () => reabrir('viaje')}
                pie={crudoViaje === 'activo' && !locked
                  ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso>
                  : undefined}
              >
                <BloqueViajeTraslado
                  lang={lang}
                  traslados={traslados}
                  checkout={checkout}
                  pedido={pedido}
                  booking={booking}
                  tiposDisponibles={tiposDisponibles}
                  tipoTraslado={tipoTraslado}
                  getPrecioDesde={getPrecioDesde}
                  onTipo={(tipo) => {
                    setTipoTraslado(tipo);
                    if (tipo !== 'redondo_aeropuerto') setFechaRegreso(null);
                    else if (!fechaRegreso) setFechaRegreso(diaSiguiente(fecha));
                  }}
                  fecha={fecha}
                  minDate={minDate}
                  onFecha={(f) => {
                    setFecha(f);
                    if (fechaRegreso && fechaRegreso <= f) setFechaRegreso(diaSiguiente(f));
                  }}
                  fechaRegreso={fechaRegreso}
                  minFechaRegreso={diaSiguiente(fecha)}
                  onFechaRegreso={setFechaRegreso}
                  hora={hora}
                  horasDisponibles={horasDisponibles}
                  onHora={setHora}
                  personas={personas}
                  maxCapacidad={maxCapacidad}
                  onPersonas={setPersonas}
                  onTopePersonas={() => ayuda.tropezar('tope-personas')}
                  error={errorPaso3}
                />
              </CheckoutSectionCard>
            </ItemPaso>

            {estadoDatos && (
              <ItemPaso unida={unidaConAnterior(secuencia, 1)}>
                <CheckoutSectionCard
                  title={checkout.stepper.datos}
                  estado={estadoDatos}
                  resumen={[resumenDatos, resumenRecogida].filter(Boolean).join(' · ')}
                  detalle={[...detalleContacto, ...(detalleRecogida ?? [])]}
                  actionLabel={locked ? undefined : etiquetaAccion(crudoDatos)}
                  onAction={locked || crudoDatos === 'activo' ? undefined : () => reabrir('datos')}
                  pie={crudoDatos === 'activo' && !locked
                    ? <BotonPaso conFlecha onClick={confirmarDatos}>{checkout.confirmStep}</BotonPaso>
                    : undefined}
                >
                  <div className="flex flex-col gap-6">
                    <BloqueContacto
                      idPrefijo="traslado"
                      checkout={checkout}
                      valores={contact}
                      errores={erroresContacto}
                      refs={{ phone: refPhone, fullName: refFullName, email: refEmail }}
                      disabled={locked}
                      onCambio={(campo, valor) => {
                        setContact((prev) => ({ ...prev, [campo]: valor }));
                        if (erroresContacto[campo]) setErroresContacto((prev) => ({ ...prev, [campo]: undefined }));
                      }}
                    />
                    <BloqueRecogida
                      traslados={traslados}
                      puntosEncuentro={catalogo.puntos_encuentro}
                      puntoSeleccionado={puntoSeleccionado}
                      puntoEncuentroId={puntoEncuentroId}
                      modoHospedaje={modoHospedaje}
                      direccionPersonalizada={direccionPersonalizada}
                      zonaPersonalizada={zonaPersonalizada}
                      tipoTraslado={tipoTraslado}
                      error={errorPaso2}
                      onPunto={setPuntoEncuentroId}
                      onOtraDireccion={() => {
                        setModoHospedaje('personalizada');
                        setPuntoEncuentroId(null);
                      }}
                      onDireccion={setDireccionPersonalizada}
                      onVolverALista={() => {
                        setModoHospedaje('catalogo');
                        setDireccionPersonalizada('');
                        setZonaPersonalizada('');
                        setPuntoEncuentroId(catalogo.puntos_encuentro[0]?.id ?? null);
                      }}
                      onZona={setZonaPersonalizada}
                    />
                  </div>
                </CheckoutSectionCard>
              </ItemPaso>
            )}
            </ReservaPlegable>

            {/* El último paso: "Cómo pagas" se pinta aquí (portal del panel) y, al crearse
                el pago, el formulario de tarjeta aparece debajo. */}
            <BloqueTarjetaPago
              lang={lang}
              checkout={checkout}
              feedback={feedback}
              ayudaMensaje={ayudaMensaje}
              mostrarDestino={actual === 'pago' || phase !== 'form'}
              destinoRef={setDestinoTarjetaPago}
              pagoEnCurso={phase === 'payment' ? pago : null}
              onPagoConfirmado={(procesando) => {
                setPagoProcesando(procesando);
                setPhase('confirmed');
              }}
            />
          </>
        }
        pedido={
          <BloquePago
            lang={lang}
            checkout={checkout}
            waiverAccepted={waiverAccepted}
            onWaiverChange={(value) => {
              setWaiverAccepted(value);
              if (value) setErrorWaiver(false);
            }}
            errorWaiver={errorWaiver}
            pago={pago}
            lineas={lines}
            nombreServicio={catalogo.servicio.nombre}
            currency={currency}
            total={total}
            montoAhora={amountDueNow}
            moneda={moneda}
            onMonedaChange={setMoneda}
            usdDisponible={usdDisponible}
            formaPago={formaPago}
            onFormaPagoChange={setFormaPagoSeleccionada}
            formaPagoDisponible={permiteAnticipo}
            codigoPromocional={codigoPromocional}
            onCodigoPromocionalChange={onCodigoPromocionalChange}
            promoEstado={promoEstado}
            promoPorcentaje={promoPorcentaje}
            destinoTarjeta={destinoTarjetaPago}
            lineasViaje={lineasViaje}
            phase={phase}
            error={error}
            feedback={feedback}
            ayudaMensaje={ayudaMensaje}
            onSubmit={iniciarPago}
            onCaptchaToken={(token) => (captchaToken.current = token)}
          />
        }
      />

      <AyudaFlotante
        visible={ayuda.visible}
        etiqueta={feedback.floatingHelp.label}
        cerrarLabel={feedback.floatingHelp.dismiss}
        mensaje={ayuda.motivo === 'tope-personas'
          ? feedback.floatingHelp.messageMaxPeople
              .replace('{name}', catalogo.servicio.nombre)
              .replace('{max}', String(maxCapacidad))
          : feedback.floatingHelp.messageValidation
              .replace('{date}', formatDay(fromLocalISODate(fecha), lang))
              .replace('{people}', String(personas))}
        onDescartar={ayuda.descartar}
      />
    </>
  );
}
