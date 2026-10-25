'use client';

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ProveedorCambioPrecio } from '@/components/checkout/cambio-precio';
import { textoRegla } from '@/lib/regla-personas';
import { useSearchParams } from 'next/navigation';
import { useBorrador } from '@/components/checkout/use-borrador';
import { useCorregir } from '@/components/checkout/use-corregir';
import { AsistenteMovil } from '@/components/reserva/asistente-movil';
import { useMovil } from '@/components/reserva/use-movil';
import { usePantallaMovil } from '@/components/reserva/use-pantalla-movil';
import { anterior as pantallaAnterior, pantallasDe, primeraDelPaso } from '@/lib/pantallas-checkout';
import { usePasoUrl } from '@/components/checkout/use-paso-url';
import { conIva, porcentajeIva } from '@/lib/iva';
import { destinoDeError } from '@/lib/campo-paso';
import { validarTodo } from '@/lib/validar-reserva';
import { claveBorrador } from '@/lib/borrador-reserva';
import { pasoDeQuery } from '@/lib/paso-url';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { ConfirmacionReserva } from '@/components/confirmacion-reserva';
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
} from '@/lib/dates';
import { horasConAnticipacion } from '@/lib/anticipacion';
import { mensajeDeFallo } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import {
  estadoDeTarjeta, estadoVisible, numeroDePaso, pasoAnterior, unidaConAnterior, type EstadoTarjeta, type EstadoVisible, type PasoId,
  rotuloDePaso,
} from '@/lib/pasos-checkout';
import { leerRef } from '@/lib/ref';
import { marcarPaginaComoConfirmacion, paginaPideConfirmacion } from '@/lib/marca-confirmacion';
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

type CampoContacto = 'phone' | 'fullName' | 'email';
const ORDEN_CAMPOS: CampoContacto[] = ['phone', 'fullName', 'email'];

type Phase = 'recuperando' | 'form' | 'submitting' | 'payment' | 'confirmed' | 'unavailable' | 'error';
type TrasladoViewProps = {
  lang: Locale;
  dict: Dictionary;
  catalogo: TrasladosCatalogo;
  empresaSlug: string;
  /** Origen de «salir» en el primer paso (`lib/origen.ts`), ya con idioma. */
  volverHref: string;
  /** `{ nombre, logo }` de la empresa de transporte (de `content/empresas`, server-only). */
  empresa?: { nombre: string; logo?: string; simbolo?: string };
};

export function TrasladoView({
  lang,
  dict,
  catalogo,
  empresaSlug,
  volverHref,
  empresa,
}: TrasladoViewProps) {
  const { checkout, traslados, feedback, pedido } = dict;
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
  // Error de la tarjeta de recogida (hotel o dirección).
  const [errorPaso2, setErrorPaso2] = useState('');

  const horasDelServicio = useMemo(() => {
    return generarHorasVentana(
      catalogo.servicio.hora_apertura,
      catalogo.servicio.hora_cierre,
      catalogo.servicio.paso_hora_minutos,
    );
  }, [catalogo.servicio.hora_apertura, catalogo.servicio.hora_cierre, catalogo.servicio.paso_hora_minutos]);
  const minDate = useMemo(() => getMinBookableDate(horasDelServicio), [horasDelServicio]);
  // «Ahora» se fija al montar: las horas que ese día no cumplen la anticipación mínima no se ofrecen.
  const [ahoraDeCarga] = useState(() => new Date());
  // `null` = el cliente borró la fecha: Continuar la pide.
  const [fecha, setFecha] = useState<string | null>(minDate);
  // El regreso es obligatorio y empieza vacío: sin respuesta se ve la pregunta, no una fecha que el
  // cliente no eligió.
  const [fechaRegreso, setFechaRegreso] = useState<string | null>(null);
  const horasDisponibles = useMemo(
    () => (fecha ? horasConAnticipacion(fecha, horasDelServicio, ahoraDeCarga) : horasDelServicio),
    [fecha, horasDelServicio, ahoraDeCarga],
  );
  const [horaElegida, setHora] = useState(horasDisponibles[0] ?? '');
  // Al cambiar de día, una hora que dejó de cumplir la anticipación pasa a la primera que sí.
  const hora = horasDisponibles.includes(horaElegida) ? horaElegida : (horasDisponibles[0] ?? horaElegida);
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

  // Borrador de la pestaña y paso en la URL (ver `use-borrador` y `use-paso-url`). Solo se repone
  // un borrador si la URL ya trae `?paso=`: una entrada nueva desde el sitio manda sobre uno viejo.
  const reponerBorrador = useSearchParams().get('paso') !== null;
  const claveDelBorrador = claveBorrador('traslados', empresaSlug);
  const borradorListo = useBorrador({
    clave: claveDelBorrador,
    habilitado: phase !== 'recuperando',
    reponer: reponerBorrador,
    terminado: phase === 'confirmed',
    estado: {
      tipoTraslado, modoHospedaje, puntoEncuentroId, direccionPersonalizada,
      fecha, fechaRegreso, hora, personas, contact, moneda, formaPagoSeleccionada, paso: actual,
    },
    restaurar: (guardado) => {
      // Una reserva recuperada del servidor ya llevó al cliente a Pago: manda sobre el borrador.
      if (actual === 'pago') return;
      setTipoTraslado(guardado.tipoTraslado);
      setModoHospedaje(guardado.modoHospedaje);
      setPuntoEncuentroId(guardado.puntoEncuentroId);
      setDireccionPersonalizada(guardado.direccionPersonalizada);
      setFecha(guardado.fecha);
      setFechaRegreso(guardado.fechaRegreso);
      setHora(guardado.hora);
      setPersonas(guardado.personas);
      setContact(guardado.contact);
      setMoneda(guardado.moneda);
      setFormaPagoSeleccionada(guardado.formaPagoSeleccionada);
      setActual(pasoDeQuery(guardado.paso) ?? 'viaje');
    },
  });
  const pagoEnCurso = phase === 'payment' || phase === 'submitting';

  // Móvil (< 640 px): asistente de una pantalla por vez (tipo, fecha, hora y pasajeros, datos,
  // recogida, cómo pagas, tarjeta). Las respuestas viven en el mismo estado.
  const movil = useMovil();
  const pantallas = useMemo(() => pantallasDe({ tipo: 'traslado' }), []);
  const asistente = usePantallaMovil({
    pantallas,
    habilitado: movil && borradorListo,
    inicial: phase === 'payment' ? 'tarjeta-0' : primeraDelPaso(pantallas, actual),
    minima: pagoEnCurso ? 'tarjeta-0' : null,
    // Sin pago creado no hay tarjeta que pedir: la pantalla más avanzada es «Cómo pagas».
    tope: phase === 'payment' ? null : 'como-pagas',
    clave: claveDelBorrador,
  });
  const { irA } = asistente;
  const irAPantallaDelCampo = useCallback(
    (destino: { paso: PasoId; campo: string }) => irA(
      destino.campo.includes('-error-') ? 'contacto'
        : destino.paso === 'datos' ? 'recogida'
          : destino.paso === 'viaje' ? 'fecha'
            : primeraDelPaso(pantallas, destino.paso),
    ),
    [irA, pantallas],
  );
  const corregir = useCorregir(actual, setEditando, movil ? irAPantallaDelCampo : undefined);
  usePasoUrl({ actual, editando, setEditando, bloqueado: pagoEnCurso, habilitado: borradorListo && !movil });
  // Una sola flecha: «paso anterior» mientras haya uno y no haya un pago en curso; si no, sale al origen.
  const pasoVisible = editando ?? actual;
  const alPasoAnterior = pagoEnCurso
    ? undefined
    : movil
      ? pantallaAnterior(pantallas, asistente.pantalla.id) !== null ? () => { asistente.retroceder(); } : undefined
      : pasoAnterior(pasoVisible) !== null ? () => setEditando(pasoAnterior(pasoVisible)) : undefined;

  useEffect(() => {
    if (!checkoutId || !recuperable) return;
    let activo = true;
    getEstadoReserva(checkoutId, empresaSlug).then((estado) => {
      if (!activo) return;
      // Una compra ya pagada solo se muestra si la URL lo pide (`?confirmacion=1`): sin la marca, esta
      // entrada es para reservar de nuevo y arranca con un formulario nuevo.
      if (estado.estado === 'cancelada' || (estado.estado === 'pagada' && !paginaPideConfirmacion())) {
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
  useEffect(() => {
    if (phase === 'confirmed') marcarPaginaComoConfirmacion();
  }, [phase]);

  // La zona cuenta en la vuelta completa (redondo con aeropuerto y de actividad); la recepción es de precio único.
  const zonaEfectiva = useMemo<Zona | ''>(() => {
    if (tipoTraslado !== 'redondo_actividad' && tipoTraslado !== 'redondo_aeropuerto') return '';
    if (modoHospedaje === 'catalogo') {
      if (puntoEncuentroId === null) return tipoTraslado === 'redondo_actividad' ? 'periferia' : '';
      const punto = catalogo.puntos_encuentro.find((p) => p.id === puntoEncuentroId);
      return punto?.zona ?? '';
    }
    // Una dirección escrita siempre se cobra como periferia (igual que `zona_efectiva` del backend).
    return 'periferia';
  }, [tipoTraslado, modoHospedaje, puntoEncuentroId, catalogo.puntos_encuentro]);

  const tarifaAplicable = useMemo(() => {
    const cabe = (t: TrasladosCatalogo['tarifas'][number]) =>
      t.tipo_traslado === tipoTraslado
      && personas >= t.personas_min
      && (t.personas_max === null || personas <= t.personas_max);
    // La tarifa de la zona del hotel; si la empresa no distingue zonas en ese tipo (zona vacía), esa (como el backend).
    return catalogo.tarifas.find((t) => cabe(t) && t.zona === zonaEfectiva)
      ?? (zonaEfectiva ? catalogo.tarifas.find((t) => cabe(t) && t.zona === '') : undefined);
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

  // El IVA se suma al final, sobre el precio ya con descuento; el anticipo se calcula sobre este total.
  const netoSinIva = precioBase !== null ? Math.max(0, precioBase - descuento) : null;
  const { iva: ivaEstimado, total } = netoSinIva === null ? { iva: 0, total: null } : conIva(netoSinIva);
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
  const formatearCambio = useCallback((monto: number) => `${currency.format(monto)} ${moneda}`, [currency, moneda]);
  // Las tarifas del tipo y la zona elegidos, por rango de pasajeros: «1–4 pasajeros: $2,700 · desde 5: $3,500».
  const reglaPasajeros = useMemo(() => {
    const delTipo = catalogo.tarifas.filter((t) => t.tipo_traslado === tipoTraslado);
    const deLaZona = delTipo.filter((t) => t.zona === zonaEfectiva);
    const rangos = (deLaZona.length > 0 ? deLaZona : delTipo.filter((t) => t.zona === ''))
      .map((t) => ({ min: t.personas_min, max: t.personas_max ?? maxCapacidad, precio: aMoneda(t.precio, moneda, catalogo.servicio.tipo_cambio_usd) }))
      .filter((r): r is { min: number; max: number; precio: number } => r.precio !== null);
    return rangos.length > 0 ? textoRegla({ tipo: 'rangos', rangos }, personas, formatearCambio, checkout.reglaPersonas) : null;
  }, [catalogo.tarifas, catalogo.servicio.tipo_cambio_usd, tipoTraslado, zonaEfectiva, maxCapacidad, moneda, personas, formatearCambio, checkout.reglaPersonas]);
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
    if (ivaEstimado > 0) {
      resultado.push({
        label: `${checkout.ivaLabel} (${porcentajeIva()} %)`,
        amount: currency.format(ivaEstimado),
        detail: '',
      });
    }
    return resultado;
  }, [precioBase, descuento, ivaEstimado, tipoTraslado, personas, traslados, checkout, promoPorcentaje, codigoPromocional, currency]);

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
    return '';
  };

  const confirmarViaje = (): boolean => {
    const falla = errorDeViaje();
    setErrorPaso3(falla);
    if (falla) {
      ayuda.tropezar('validacion');
      return false;
    }
    setActual((a) => (a === 'viaje' ? 'datos' : a));
    setEditando(null);
    return true;
  };

  /** «Tus datos» junta contacto y recogida: se validan juntos antes de pasar al pago. */
  const confirmarDatos = (): boolean => {
    const errs = validarContacto();
    setErroresContacto(errs);
    const falla = errorDeRecogida();
    setErrorPaso2(falla);
    if (Object.keys(errs).length > 0) {
      ayuda.tropezar('validacion');
      const primero = ORDEN_CAMPOS.find((c) => errs[c]);
      if (primero) refsContacto[primero].current?.focus();
      return false;
    }
    if (falla) {
      ayuda.tropezar('validacion');
      return false;
    }
    setActual((a) => (a === 'datos' ? 'pago' : a));
    setEditando(null);
    return true;
  };

  /** Solo el contacto (en móvil la recogida tiene su propia pantalla). */
  const confirmarContacto = (): boolean => {
    const errs = validarContacto();
    setErroresContacto(errs);
    const primero = ORDEN_CAMPOS.find((c) => errs[c]);
    if (!primero) return true;
    ayuda.tropezar('validacion');
    refsContacto[primero].current?.focus();
    return false;
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
    setErrorPaso3(fallaViaje);
    const errs = validarContacto();
    setErroresContacto(errs);
    const fallaRecogida = errorDeRecogida();
    setErrorPaso2(fallaRecogida);
    const primerContacto = ORDEN_CAMPOS.find((c) => errs[c]);
    const problema = validarTodo([
      fallaViaje ? { paso: 'viaje', campo: '', mensaje: fallaViaje } : null,
      primerContacto ? { paso: 'datos', campo: `traslado-error-${primerContacto}`, mensaje: errs[primerContacto] ?? '' } : null,
      fallaRecogida ? { paso: 'datos', campo: '', mensaje: fallaRecogida } : null,
    ]);
    if (problema) {
      ayuda.tropezar('validacion');
      corregir(problema);
      return;
    }
    if (!waiverAccepted) {
      ayuda.tropezar('validacion');
      setErrorWaiver(true);
      return;
    }
    if (phase === 'submitting' || phase === 'payment') return;
    // `errorDeViaje` ya lo pidió; esto solo lo asegura para el tipo.
    if (!fecha) return;

    setPhase('submitting');
    setError('');

    try {
      const payload: ReservaTrasladoInput = {
        checkout_id: checkoutId,
        servicio: catalogo.servicio.slug,
        tipo_traslado: tipoTraslado,
        punto_encuentro: modoHospedaje === 'catalogo' ? puntoEncuentroId : undefined,
        direccion_personalizada: modoHospedaje === 'personalizada' ? direccionPersonalizada.trim() : '',
        zona: modoHospedaje === 'personalizada' && (tipoTraslado === 'redondo_actividad' || tipoTraslado === 'redondo_aeropuerto') ? 'periferia' : undefined,
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
      // Creado el pago, el asistente móvil pasa a la tarjeta.
      if (movil) irA('tarjeta-0');
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
      // El servidor rechazó un campo concreto: se lleva al cliente a su paso y a su control.
      const destino = err instanceof ApiError && err.status === 400 ? destinoDeError(err.detail, 'traslado') : null;
      if (destino) corregir(destino);
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
      : direccionPersonalizada;
  const fechaTexto = fecha ? formatDay(fromLocalISODate(fecha), lang) : checkout.calendario.sinFecha;

  const locked = phase === 'submitting' || phase === 'payment' || phase === 'unavailable';

  if (phase === 'recuperando') return null;

  if (phase === 'confirmed') {
    return (
      <ConfirmacionReserva
        lang={lang}
        dict={dict}
        datos={{
          folio: reservaId!,
          procesando: pagoProcesando,
          nombre: contact.fullName,
          email: contact.email,
          color: 'traslado',
          titulo: traslados.types[tipoTraslado]?.title ?? tipoTraslado,
          empresas: empresa ? [empresa.nombre] : [],
          fecha: fechaTexto,
          lineas: [
            { etiqueta: checkout.dayLabel, valor: fechaTexto },
            tipoTraslado === 'redondo_aeropuerto' && fechaRegreso
              ? { etiqueta: traslados.fields.fechaRegreso, valor: formatDay(fromLocalISODate(fechaRegreso), lang) }
              : null,
            { etiqueta: checkout.hourLabel, valor: formatHour(hora) },
            { etiqueta: traslados.fields.pasajeros, valor: String(personas) },
            resumenRecogida ? { etiqueta: traslados.fields.dondeRecogemos, valor: resumenRecogida } : null,
          ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null),
          extras: [],
          pagado: total !== null ? currency.format(total) : null,
          saldoEnEfectivo: null,
          encuentro: null,
        }}
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

  const pasoActualStepper = movil
    ? numeroDePaso(asistente.pantalla.paso)
    : phase === 'submitting' || phase === 'payment' ? numeroDePaso('pago') : numeroDePaso(actual);
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
    // Antes de crear el pago, el anticipo elegido en «Cómo pagas» ya cambia la cifra (en móvil, la de la barra).
    : amountDueNow !== null && total !== null && amountDueNow < total
      ? {
          actual: pasoActualStepper,
          totalMovil: `${currency.format(amountDueNow)} ${moneda}`,
          rotulo: checkout.stepper.payNow,
          totalGeneral: `${currency.format(total)} ${moneda}`,
        }
      : { actual: pasoActualStepper, totalMovil };

  const recogidaElegida = actual === 'pago' || phase !== 'form';
  const lineasViaje = [
    { etiqueta: traslados.step1Title, valor: traslados.types[tipoTraslado]?.title ?? tipoTraslado },
    { etiqueta: checkout.summary.date, valor: fechaTexto },
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

  const ayudaMensaje = `Hola, necesito ayuda con mi reserva de traslado ${tipoTraslado} para ${personas} personas el ${fecha ?? ''}.`;

  // Los mismos bloques en las tarjetas de escritorio y en las pantallas del asistente móvil.
  const bloqueViajeTraslado = (parte?: 'tipo' | 'fecha' | 'hora-pasajeros') => (
    <BloqueViajeTraslado
      lang={lang}
      traslados={traslados}
      checkout={checkout}
      pedido={pedido}
      tiposDisponibles={tiposDisponibles}
      tipoTraslado={tipoTraslado}
      getPrecioDesde={getPrecioDesde}
      onTipo={(tipo) => {
        setTipoTraslado(tipo);
        if (tipo !== 'redondo_aeropuerto') setFechaRegreso(null);
      }}
      fecha={fecha}
      minDate={minDate}
      fechaRegreso={fechaRegreso}
      onFechas={({ desde, hasta }) => {
        setFecha(desde);
        if (tipoTraslado === 'redondo_aeropuerto') setFechaRegreso(hasta);
      }}
      hora={hora}
      horasDisponibles={horasDisponibles}
      onHora={setHora}
      personas={personas}
      maxCapacidad={maxCapacidad}
      onPersonas={setPersonas}
      onTopePersonas={() => ayuda.tropezar('tope-personas')}
      reglaPersonas={reglaPasajeros}
      error={errorPaso3}
      parte={parte}
    />
  );
  const bloqueContacto = (
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
  );
  const bloqueRecogida = (
    <BloqueRecogida
      traslados={traslados}
      puntosEncuentro={catalogo.puntos_encuentro}
      puntoSeleccionado={puntoSeleccionado}
      puntoEncuentroId={puntoEncuentroId}
      modoHospedaje={modoHospedaje}
      direccionPersonalizada={direccionPersonalizada}
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
        setPuntoEncuentroId(catalogo.puntos_encuentro[0]?.id ?? null);
      }}
    />
  );
  const bloqueTarjetaPago = (mostrarDestino: boolean, pagoEnCurso: Pago | null) => (
    <BloqueTarjetaPago
      lang={lang}
      checkout={checkout}
      feedback={feedback}
      ayudaMensaje={ayudaMensaje}
      mostrarDestino={mostrarDestino}
      destinoRef={setDestinoTarjetaPago}
      pagoEnCurso={pagoEnCurso}
      onPagoConfirmado={(procesando) => {
        setPagoProcesando(procesando);
        setPhase('confirmed');
      }}
    />
  );

  // Móvil: una pantalla por vez. «Cómo pagas» y la tarjeta traen su propio botón (el de la tarjeta
  // «Cómo pagas» llega a la barra por portal; el de Stripe, dentro del formulario).
  const pantalla = asistente.pantalla;
  const continuar = checkout.barra.continuar;
  const pantallaMovil = (() => {
    switch (pantalla.tipo) {
      case 'tipo':
        return { titulo: traslados.step1Title, contenido: bloqueViajeTraslado('tipo'), accion: {
          etiqueta: continuar, alPulsar: () => asistente.avanzar(),
        } };
      case 'fecha':
        return { titulo: checkout.barra.fechaTraslado, contenido: bloqueViajeTraslado('fecha'), accion: {
          etiqueta: continuar,
          alPulsar: () => {
            const falla = errorDeViaje();
            setErrorPaso3(falla);
            if (falla) ayuda.tropezar('validacion');
            else asistente.avanzar();
          },
        } };
      case 'hora-pasajeros':
        return { titulo: checkout.barra.horaPasajeros, contenido: bloqueViajeTraslado('hora-pasajeros'), accion: {
          etiqueta: continuar,
          alPulsar: () => {
            if (confirmarViaje()) asistente.avanzar();
            else irA('fecha');
          },
        } };
      case 'contacto':
        return { titulo: checkout.stepper.datos, contenido: bloqueContacto, accion: {
          etiqueta: continuar, alPulsar: () => { if (confirmarContacto()) asistente.avanzar(); },
        } };
      case 'recogida':
        return { titulo: traslados.fields.dondeRecogemos, contenido: bloqueRecogida, accion: {
          etiqueta: continuar, alPulsar: () => { if (confirmarDatos()) asistente.avanzar(); },
        } };
      case 'como-pagas':
        return { titulo: checkout.howYouPay, contenido: bloqueTarjetaPago(true, null) };
      default:
        return { titulo: checkout.barra.tarjeta, contenido: bloqueTarjetaPago(false, phase === 'payment' ? pago : null), accion: {
          etiqueta: checkout.confirmPay, alPulsar: () => {}, deshabilitado: true, razon: checkout.barra.cargandoPago,
        } };
    }
  })();
  const asistenteMovil = (
    <AsistenteMovil
      id={pantalla.id}
      titulo={pantallaMovil.titulo}
      soloFundido={pantalla.paso === 'pago'}
      anuncio={`${rotuloDePaso(checkout.stepper.stepOf, pantalla.paso)}: ${checkout.stepper[pantalla.paso]}`}
      accion={pantallaMovil.accion}
    >
      {pantallaMovil.contenido}
    </AsistenteMovil>
  );

  return (
    <ProveedorCambioPrecio total={total} formatear={formatearCambio} textos={checkout.cambioPrecio}>
    <>
      <PaginaCheckout
        lang={lang}
        dict={dict}
        volverHref={volverHref}
        alPasoAnterior={alPasoAnterior}
        empresa={empresa}
        empresasDeslinde={[empresaSlug]}
        volverLabel={traslados.back}
        encabezado={
          <EncabezadoCompra
            titulo={checkout.tituloPagina}
            detalle={traslados.title}
          />
        }
        stepper={{ ...stepperPago, steps: stepsList }}
        pasos={movil ? asistenteMovil : (
          <>
            <ReservaPlegable
              activo={phase === 'payment'}
              titulo={dict.pedido.yourBooking}
              etiquetaEstado={dict.pedido.bookingSaved}
              notaBloqueada={dict.pedido.lockedNote}
              ctaAyuda={dict.pedido.lockedCta}
              mensajeAyuda={ayudaMensaje}
            >
            <ItemPaso unida={unidaConAnterior(secuencia, 0)}>
              <CheckoutSectionCard
                title={checkout.tripHeadline}
                paso="viaje"
                estado={estadoViaje}
                detalle={detalleViaje}
                actionLabel={locked ? undefined : etiquetaAccion(crudoViaje)}
                onAction={locked || crudoViaje === 'activo' ? undefined : () => reabrir('viaje')}
                pie={crudoViaje === 'activo' && !locked
                  ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso>
                  : undefined}
              >
                {bloqueViajeTraslado()}
              </CheckoutSectionCard>
            </ItemPaso>

            {estadoDatos && (
              <ItemPaso unida={unidaConAnterior(secuencia, 1)}>
                <CheckoutSectionCard
                  title={checkout.stepper.datos}
                  paso="datos"
                  estado={estadoDatos}
                  detalle={[...detalleContacto, ...(detalleRecogida ?? [])]}
                  actionLabel={locked ? undefined : etiquetaAccion(crudoDatos)}
                  onAction={locked || crudoDatos === 'activo' ? undefined : () => reabrir('datos')}
                  pie={crudoDatos === 'activo' && !locked
                    ? <BotonPaso conFlecha onClick={confirmarDatos}>{checkout.confirmStep}</BotonPaso>
                    : undefined}
                >
                  <div className="flex flex-col gap-6">
                    {bloqueContacto}
                    {bloqueRecogida}
                  </div>
                </CheckoutSectionCard>
              </ItemPaso>
            )}
            </ReservaPlegable>

            {/* El último paso: "Cómo pagas" se pinta aquí (portal del panel) y, al crearse
                el pago, el formulario de tarjeta aparece debajo. */}
            {bloqueTarjetaPago(actual === 'pago' || phase !== 'form', phase === 'payment' ? pago : null)}
          </>
        )}
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
            sellos={empresa ? [empresa] : undefined}
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
              .replace('{date}', fechaTexto)
              .replace('{people}', String(personas))}
        onDescartar={ayuda.descartar}
      />
    </>
    </ProveedorCambioPrecio>
  );
}
