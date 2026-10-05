'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Buildings,
  EnvelopeSimple,
  ListBullets,
  MapPin,
  Phone,
  User,
} from '@phosphor-icons/react';
import { motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BookingConfirmation } from '@/components/booking-confirmation';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CheckoutStepper } from '@/components/checkout-stepper';
import { DateField } from '@/components/date-field';
import { CLASES_CAMPO_CON_ERROR, ErrorDeCampo, propsDeError } from '@/components/field-error';
import { FieldPopover } from '@/components/field-popover';
import { PeopleStepper } from '@/components/people-stepper';
import { SiteHeader } from '@/components/site-header';
import { FormularioPago, StripePanel } from '@/components/stripe-panel';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
import { TipoTrasladoCards } from '@/components/checkout/tipo-traslado-cards';
import { TimeField } from '@/components/time-field';
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

function formatDay(date: Date, lang: Locale) {
  const locale = intlLocale(lang);
  const weekday = new Intl.DateTimeFormat(locale, { weekday: 'long' }).format(date);
  const month = new Intl.DateTimeFormat(locale, { month: 'long' }).format(date);
  const day = String(date.getDate()).padStart(2, '0');
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  return lang === 'es'
    ? `${cap(weekday)} ${day} de ${cap(month)}`
    : `${cap(weekday)}, ${cap(month)} ${day}`;
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
  const { checkout, traslados, feedback, nav, footer, booking } = dict;
  const { mostrar } = useToast();
  const sinMovimiento = useReducedMotion();

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

  const [pasosVisibles, setPasosVisibles] = useState(1);
  const [pasoEditando, setPasoEditando] = useState<number | null>(null);

  const [tipoTraslado, setTipoTraslado] = useState<TipoTraslado>('redondo_aeropuerto');

  const [modoHospedaje, setModoHospedaje] = useState<'catalogo' | 'personalizada'>('catalogo');
  const [puntoEncuentroId, setPuntoEncuentroId] = useState<number | null>(() => {
    return catalogo.puntos_encuentro[0]?.id ?? null;
  });
  const [direccionPersonalizada, setDireccionPersonalizada] = useState('');
  const [zonaPersonalizada, setZonaPersonalizada] = useState<Zona | ''>('');
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

  const [moneda, setMoneda] = useState<Moneda>('MXN');
  const usdDisponible = Number(catalogo.tipo_cambio_usd) > 0;

  const permiteAnticipo = catalogo.servicio.permite_anticipo;
  const [formaPagoSeleccionada, setFormaPagoSeleccionada] = useState<'completo' | 'anticipo'>('completo');
  const formaPago = permiteAnticipo ? formaPagoSeleccionada : 'completo';
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [errorWaiver, setErrorWaiver] = useState(false);
  const captchaToken = useRef('');

  const [codigoPromocional, setCodigoPromocional] = useState('');
  const [promoEstado, setPromoEstado] = useState<'idle' | 'verificando' | 'valido' | 'invalido'>('idle');
  const [promoPorcentaje, setPromoPorcentaje] = useState<string | null>(null);

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
      setPasosVisibles(5);
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
    return aMoneda(tarifaAplicable.precio, moneda, catalogo.tipo_cambio_usd);
  }, [tarifaAplicable, moneda, catalogo.tipo_cambio_usd]);

  const descuento = useMemo(() => {
    if (promoEstado === 'valido' && promoPorcentaje && precioBase !== null) {
      return (precioBase * parseFloat(promoPorcentaje)) / 100;
    }
    return 0;
  }, [promoEstado, promoPorcentaje, precioBase]);

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

  const confirmarPaso1 = () => {
    setPasosVisibles((v) => Math.max(v, 2));
    if (pasoEditando === 1) setPasoEditando(null);
  };

  const confirmarPaso2 = () => {
    setErrorPaso2('');
    if (modoHospedaje === 'catalogo') {
      if (puntoEncuentroId === null) {
        setErrorPaso2(traslados.errors.seleccionaHospedaje);
        return;
      }
    } else {
      if (!direccionPersonalizada.trim()) {
        setErrorPaso2(traslados.errors.seleccionaHospedaje);
        return;
      }
      if (tipoTraslado === 'redondo_actividad' && !zonaPersonalizada) {
        setErrorPaso2(traslados.errors.seleccionaZona);
        return;
      }
    }
    setPasosVisibles((v) => Math.max(v, 3));
    if (pasoEditando === 2) setPasoEditando(null);
  };

  const confirmarPaso3 = () => {
    setErrorPaso3('');
    if (!fecha) {
      setErrorPaso3(traslados.errors.seleccionaFecha);
      return;
    }
    if (tipoTraslado === 'redondo_aeropuerto') {
      if (!fechaRegreso) {
        setErrorPaso3(traslados.errors.seleccionaFechaRegreso);
        return;
      }
      if (fechaRegreso <= fecha) {
        setErrorPaso3(traslados.errors.fechaRegresoPosterior);
        return;
      }
    }
    setPasosVisibles((v) => Math.max(v, 4));
    if (pasoEditando === 3) setPasoEditando(null);
  };

  const confirmarPaso4 = () => {
    setPasosVisibles((v) => Math.max(v, 5));
    if (pasoEditando === 4) setPasoEditando(null);
  };

  const onCodigoPromocionalChange = (codigo: string) => {
    setCodigoPromocional(codigo);
    if (!codigo.trim()) {
      setPromoEstado('idle');
      setPromoPorcentaje(null);
      return;
    }
    setPromoEstado('verificando');
    validarCodigoPromocional(codigo, contact.email, empresaSlug)
      .then((res) => {
        if (res.valido && res.porcentaje_descuento) {
          setPromoEstado('valido');
          setPromoPorcentaje(res.porcentaje_descuento);
        } else {
          setPromoEstado('invalido');
          setPromoPorcentaje(null);
        }
      })
      .catch(() => {
        setPromoEstado('invalido');
        setPromoPorcentaje(null);
      });
  };

  const iniciarPago = async () => {
    const errs = validarContacto();
    setErroresContacto(errs);
    if (Object.keys(errs).length > 0) {
      const primero = ORDEN_CAMPOS.find((c) => errs[c]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }
    if (!waiverAccepted) {
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

  const resumenPaso1 = traslados.types[tipoTraslado]?.title ?? tipoTraslado;

  const puntoSeleccionado = catalogo.puntos_encuentro.find((p) => p.id === puntoEncuentroId);
  const resumenPaso2 =
    modoHospedaje === 'catalogo'
      ? (puntoSeleccionado?.nombre ?? '')
      : `${direccionPersonalizada}${zonaPersonalizada ? ` (${zonaPersonalizada})` : ''}`;

  const resumenPaso3 = `${formatDay(fromLocalISODate(fecha), lang)} · ${formatHour(hora)}${
    tipoTraslado === 'redondo_aeropuerto' && fechaRegreso
      ? ` | ${traslados.fields.fechaRegreso}: ${formatDay(fromLocalISODate(fechaRegreso), lang)}`
      : ''
  }`;

  const resumenPaso4 = `${personas} ${traslados.fields.pasajeros.toLowerCase()}`;

  const colapsado1 = pasosVisibles > 1 && pasoEditando !== 1;
  const colapsado2 = pasosVisibles > 2 && pasoEditando !== 2;
  const colapsado3 = pasosVisibles > 3 && pasoEditando !== 3;
  const colapsado4 = pasosVisibles > 4 && pasoEditando !== 4;

  const pasoActualStepper = phase === 'confirmed' ? 5 : pasoEditando ?? pasosVisibles;

  const stepsList = [
    traslados.step1Title,
    traslados.step2Title,
    traslados.step3Title,
    traslados.step4Title,
    traslados.step5Title,
  ];
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
        pagado={total !== null ? currency.format(total) : '—'}
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
    const precios = tarifasTipo.map((t) => aMoneda(t.precio, moneda, catalogo.tipo_cambio_usd));
    if (precios.some((p) => p === null)) return null;
    const min = Math.min(...precios as number[]);
    return currency.format(min);
  };

  const hrefVolver = sedeSlugActual ? `/${lang}/sede/${sedeSlugActual}` : `/${lang}`;

  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlugActual} />

      <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
        <Link
          href={hrefVolver}
          className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {traslados.back}
        </Link>
      </div>

      <div className="mx-auto max-w-6xl px-6 pt-6 sm:px-8 lg:px-12">
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          {traslados.title}
        </h1>
        <p className="mt-1 text-sm text-muted">{traslados.subtitle}</p>
      </div>

      <CheckoutStepper stepper={checkout.stepper} actual={pasoActualStepper} steps={stepsList} />

      <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex min-w-0 flex-col gap-6">
          {/* PASO 1: Tipo de traslado */}
          <CheckoutSectionCard
            title={traslados.step1Title}
            estado={colapsado1 ? 'completado' : pasoEditando === 1 ? 'editando' : 'activo'}
            resumen={resumenPaso1}
            actionLabel={colapsado1 ? checkout.changeStep : pasoEditando === 1 ? checkout.doneEditing : undefined}
            onAction={() => setPasoEditando(colapsado1 ? 1 : null)}
          >
            <p className="mb-4 text-xs text-muted">{traslados.step1Description}</p>
            <TipoTrasladoCards
              tipos={tiposDisponibles}
              valor={tipoTraslado}
              textos={traslados.types}
              etiqueta={traslados.step1Title}
              precioDesde={getPrecioDesde}
              onChange={(tipo) => {
                setTipoTraslado(tipo);
                if (tipo !== 'redondo_aeropuerto') setFechaRegreso(null);
                else if (!fechaRegreso) setFechaRegreso(diaSiguiente(fecha));
              }}
            />

            {pasosVisibles === 1 && (
              <div className="mt-6 flex justify-end border-t border-border pt-5">
                <button
                  type="button"
                  onClick={confirmarPaso1}
                  className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]"
                >
                  {checkout.confirmStep}
                </button>
              </div>
            )}
          </CheckoutSectionCard>

          {/* PASO 2: Punto de encuentro u hospedaje */}
          {pasosVisibles < 2 ? null : (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              <CheckoutSectionCard
                title={traslados.step2Title}
                estado={colapsado2 ? 'completado' : pasoEditando === 2 ? 'editando' : 'activo'}
                resumen={resumenPaso2}
                actionLabel={colapsado2 ? checkout.changeStep : pasoEditando === 2 ? checkout.doneEditing : undefined}
                onAction={() => setPasoEditando(colapsado2 ? 2 : null)}
              >
                <p className="mb-4 text-xs text-muted">{traslados.step2Description}</p>

                {modoHospedaje === 'catalogo' ? (
                  <div className="flex flex-col gap-3">
                    <FieldPopover
                      label={traslados.fields.puntoEncuentro}
                      value={puntoSeleccionado?.nombre ?? ''}
                      vacio={puntoEncuentroId === null}
                      placeholder={traslados.fields.puntoEncuentroPlaceholder}
                      icon={<Buildings size={20} className="shrink-0 text-muted" />}
                    >
                      {(cerrar) => (
                        <div className="w-full sm:w-80 max-h-72 overflow-y-auto">
                          <p className="px-2 pb-2 text-xs font-semibold text-muted uppercase tracking-wider">
                            {traslados.fields.puntoEncuentro}
                          </p>
                          <ul className="flex flex-col gap-1">
                            {catalogo.puntos_encuentro.map((p) => {
                              const sel = p.id === puntoEncuentroId;
                              return (
                                <li key={p.id}>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setPuntoEncuentroId(p.id);
                                      cerrar();
                                    }}
                                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm text-left transition-colors ${
                                      sel
                                        ? 'bg-accent font-medium text-accent-foreground'
                                        : 'text-foreground hover:bg-background'
                                    }`}
                                  >
                                    <span className="truncate pr-2">{p.nombre}</span>
                                    <span className="shrink-0 text-[10px] font-medium tracking-wide uppercase opacity-75">
                                      {p.zona}
                                    </span>
                                  </button>
                                </li>
                              );
                            })}
                          </ul>
                          {/* Opción más de ESTA pregunta: va donde el cliente ya busca. */}
                          <button
                            type="button"
                            onClick={() => {
                              setModoHospedaje('personalizada');
                              setPuntoEncuentroId(null);
                              cerrar();
                            }}
                            className="mt-2 flex w-full items-center gap-2 rounded-lg border-t border-border px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-background"
                          >
                            <MapPin size={16} className="shrink-0 text-muted" />
                            {traslados.fields.otraDireccionOpcion}
                          </button>
                        </div>
                      )}
                    </FieldPopover>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    <label className="flex flex-col gap-1.5 text-sm">
                      <span className="text-muted">{traslados.fields.otraDireccion}</span>
                      <div className="relative">
                        <MapPin
                          size={18}
                          className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
                        />
                        <input
                          type="text"
                          value={direccionPersonalizada}
                          onChange={(e) => setDireccionPersonalizada(e.target.value)}
                          placeholder={traslados.fields.direccionPlaceholder}
                          className="w-full border border-border bg-surface py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent"
                        />
                      </div>
                    </label>

                    {tipoTraslado === 'redondo_actividad' && (
                      <div className="flex flex-col gap-2 rounded-xl border border-border bg-background p-4">
                        <span className="text-xs font-semibold text-foreground">
                          {traslados.fields.zona}
                        </span>
                        <p className="text-xs text-muted">{traslados.fields.zonaRequiredNotice}</p>
                        <div className="mt-1 grid grid-cols-2 gap-3">
                          {(['centro', 'periferia'] as const).map((z) => (
                            <label
                              key={z}
                              className={`flex items-center gap-2.5 rounded-lg border p-3 text-sm cursor-pointer transition-colors ${
                                zonaPersonalizada === z
                                  ? 'border-accent bg-surface font-medium text-foreground ring-1 ring-accent'
                                  : 'border-border text-muted hover:border-border-strong'
                              }`}
                            >
                              <input
                                type="radio"
                                name="zona-personalizada"
                                value={z}
                                checked={zonaPersonalizada === z}
                                onChange={() => setZonaPersonalizada(z)}
                                className="h-4 w-4 accent-accent"
                              />
                              <span>
                                {z === 'centro'
                                  ? traslados.fields.zonaCentro
                                  : traslados.fields.zonaPeriferia}
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    <AccionTexto
                      icono={<ListBullets size={14} />}
                      onClick={() => {
                        setModoHospedaje('catalogo');
                        setDireccionPersonalizada('');
                        setZonaPersonalizada('');
                        setPuntoEncuentroId(catalogo.puntos_encuentro[0]?.id ?? null);
                      }}
                    >
                      {traslados.fields.volverALista}
                    </AccionTexto>
                  </div>
                )}

                <ErrorDeCampo id="error-paso2" mensaje={errorPaso2} className="mt-2.5" />

                {(pasosVisibles === 2 || pasoEditando === 2) && (
                  <div className="mt-6 flex justify-end border-t border-border pt-5">
                    <button
                      type="button"
                      onClick={confirmarPaso2}
                      className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]"
                    >
                      {checkout.confirmStep}
                    </button>
                  </div>
                )}
              </CheckoutSectionCard>
            </motion.div>
          )}
          {/* PASO 3: Fechas y horario */}
          {pasosVisibles < 3 ? null : (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              <CheckoutSectionCard
                title={traslados.step3Title}
                estado={colapsado3 ? 'completado' : pasoEditando === 3 ? 'editando' : 'activo'}
                resumen={resumenPaso3}
                actionLabel={colapsado3 ? checkout.changeStep : pasoEditando === 3 ? checkout.doneEditing : undefined}
                onAction={() => setPasoEditando(colapsado3 ? 3 : null)}
              >
                <p className="mb-4 text-xs text-muted">{traslados.step3Description}</p>

                <div className="flex flex-col gap-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <DateField
                      lang={lang}
                      label={traslados.fields.fecha}
                      value={fecha}
                      onChange={(f) => {
                        setFecha(f);
                        if (fechaRegreso && fechaRegreso <= f) {
                          setFechaRegreso(diaSiguiente(f));
                        }
                      }}
                      minDate={minDate}
                      prevMonthLabel={booking.prevMonth}
                      nextMonthLabel={booking.nextMonth}
                      personas={personas}
                      fullLabel={checkout.dayFull}
                      sinCupo={true}
                    />

                    <TimeField
                      label={traslados.fields.hora}
                      help={checkout.hourLabel}
                      value={hora}
                      onChange={setHora}
                      availableHours={horasDisponibles}
                    />
                  </div>

                  {tipoTraslado === 'redondo_aeropuerto' && (
                    <div className="border-t border-border pt-4">
                      <DateField
                        lang={lang}
                        label={traslados.fields.fechaRegreso}
                        value={fechaRegreso}
                        onChange={setFechaRegreso}
                        minDate={diaSiguiente(fecha)}
                        prevMonthLabel={booking.prevMonth}
                        nextMonthLabel={booking.nextMonth}
                        personas={personas}
                        fullLabel={checkout.dayFull}
                        sinCupo={true}
                      />
                    </div>
                  )}
                </div>

                <ErrorDeCampo id="error-paso3" mensaje={errorPaso3} className="mt-2.5" />

                {(pasosVisibles === 3 || pasoEditando === 3) && (
                  <div className="mt-6 flex justify-end border-t border-border pt-5">
                    <button
                      type="button"
                      onClick={confirmarPaso3}
                      className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]"
                    >
                      {checkout.confirmStep}
                    </button>
                  </div>
                )}
              </CheckoutSectionCard>
            </motion.div>
          )}

          {/* PASO 4: Pasajeros */}
          {pasosVisibles < 4 ? null : (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              <CheckoutSectionCard
                title={traslados.step4Title}
                estado={colapsado4 ? 'completado' : pasoEditando === 4 ? 'editando' : 'activo'}
                resumen={resumenPaso4}
                actionLabel={colapsado4 ? checkout.changeStep : pasoEditando === 4 ? checkout.doneEditing : undefined}
                onAction={() => setPasoEditando(colapsado4 ? 4 : null)}
              >
                <p className="mb-4 text-xs text-muted">{traslados.step4Description}</p>

                <div className="rounded-xl border border-border bg-surface p-2">
                  <PeopleStepper
                    label={traslados.fields.pasajeros}
                    value={personas}
                    onChange={setPersonas}
                    maxPeople={maxCapacidad}
                    minPeople={1}
                    maxNotice={traslados.fields.maxPasajerosNotice.replace('{max}', String(maxCapacidad))}
                  />
                </div>

                {(pasosVisibles === 4 || pasoEditando === 4) && (
                  <div className="mt-6 flex justify-end border-t border-border pt-5">
                    <button
                      type="button"
                      onClick={confirmarPaso4}
                      className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]"
                    >
                      {checkout.confirmStep}
                    </button>
                  </div>
                )}
              </CheckoutSectionCard>
            </motion.div>
          )}

          {/* PASO 5: Contacto */}
          {pasosVisibles < 5 ? null : (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              <CheckoutSectionCard title={traslados.step5Title} estado="activo">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="flex flex-col gap-1.5 text-sm sm:col-span-1">
                    <span className="text-muted">{checkout.phone}</span>
                    <span className="relative">
                      <Phone
                        size={18}
                        className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
                      />
                      <input
                        ref={refPhone}
                        type="tel"
                        required
                        disabled={phase === 'submitting' || phase === 'payment'}
                        value={contact.phone}
                        onChange={(e) => {
                          setContact((prev) => ({ ...prev, phone: e.target.value }));
                          if (erroresContacto.phone)
                            setErroresContacto((prev) => ({ ...prev, phone: undefined }));
                        }}
                        {...propsDeError('error-phone', Boolean(erroresContacto.phone))}
                        className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                          erroresContacto.phone
                            ? CLASES_CAMPO_CON_ERROR
                            : 'border-border focus:border-accent'
                        }`}
                      />
                    </span>
                    <ErrorDeCampo id="error-phone" mensaje={erroresContacto.phone} />
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm sm:col-span-1">
                    <span className="text-muted">{checkout.fullName}</span>
                    <span className="relative">
                      <User
                        size={18}
                        className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
                      />
                      <input
                        ref={refFullName}
                        type="text"
                        required
                        disabled={phase === 'submitting' || phase === 'payment'}
                        value={contact.fullName}
                        onChange={(e) => {
                          setContact((prev) => ({ ...prev, fullName: e.target.value }));
                          if (erroresContacto.fullName)
                            setErroresContacto((prev) => ({ ...prev, fullName: undefined }));
                        }}
                        {...propsDeError('error-fullName', Boolean(erroresContacto.fullName))}
                        className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                          erroresContacto.fullName
                            ? CLASES_CAMPO_CON_ERROR
                            : 'border-border focus:border-accent'
                        }`}
                      />
                    </span>
                    <ErrorDeCampo id="error-fullName" mensaje={erroresContacto.fullName} />
                  </label>

                  <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
                    <span className="text-muted">{checkout.email}</span>
                    <span className="relative">
                      <EnvelopeSimple
                        size={18}
                        className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
                      />
                      <input
                        ref={refEmail}
                        type="email"
                        required
                        disabled={phase === 'submitting' || phase === 'payment'}
                        value={contact.email}
                        onChange={(e) => {
                          setContact((prev) => ({ ...prev, email: e.target.value }));
                          if (erroresContacto.email)
                            setErroresContacto((prev) => ({ ...prev, email: undefined }));
                        }}
                        {...propsDeError('error-email', Boolean(erroresContacto.email))}
                        className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                          erroresContacto.email
                            ? CLASES_CAMPO_CON_ERROR
                            : 'border-border focus:border-accent'
                        }`}
                      />
                    </span>
                    <ErrorDeCampo id="error-email" mensaje={erroresContacto.email} />
                  </label>
                </div>

                <div className="mt-6 rounded-xl border border-border bg-background p-4 text-xs text-muted leading-relaxed">
                  <span className="font-semibold text-foreground block mb-1">
                    {traslados.summary.transfer}
                  </span>
                  {traslados.summary.included}
                </div>
              </CheckoutSectionCard>
            </motion.div>
          )}

          {/* El último paso: "Cómo pagas" se pinta aquí (portal del panel) y, al crearse
              el pago, el formulario de tarjeta aparece debajo. */}
          {(pasosVisibles >= 5 || phase !== 'form') && <div className={phase === 'payment' ? '-mt-[calc(1.5rem+1px)]' : undefined} ref={setDestinoTarjetaPago} />}

          {phase === 'payment' && pago && (
            <FormularioPago
              checkout={checkout}
              feedback={feedback}
              ayudaMensaje={`Hola, necesito ayuda con mi reserva de traslado ${tipoTraslado} para ${personas} personas el ${fecha}.`}
              pago={pago}
              onPagoConfirmado={(procesando) => {
                setPagoProcesando(procesando);
                setPhase('confirmed');
              }}
            />
          )}
        </div>

        {/* Panel de resumen y pago */}
        <div className="min-w-0">
          <div className="scroll-mt-28">
            <StripePanel
              lang={lang}
              checkout={checkout}
              waiverAccepted={waiverAccepted}
              onWaiverChange={(value) => {
                setWaiverAccepted(value);
                if (value) setErrorWaiver(false);
              }}
              errorWaiver={errorWaiver}
              lines={pago ? [{
                label: catalogo.servicio.nombre,
                amount: currency.format(Number(pago.precio_total)),
              }] : lines}
              total={pago ? currency.format(Number(pago.precio_total)) : total === null ? '—' : currency.format(total)}
              amountDueNow={pago ? currency.format(Number(pago.monto_a_cobrar)) : amountDueNow === null ? '—' : currency.format(amountDueNow)}
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
              phase={phase}
              error={error}
              feedback={feedback}
              ayudaMensaje={`Hola, necesito ayuda con mi reserva de traslado ${tipoTraslado} para ${personas} personas el ${fecha}.`}
              onSubmit={iniciarPago}
              onCaptchaToken={(token) => (captchaToken.current = token)}
            />

          </div>
        </div>
      </main>

      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );
}
