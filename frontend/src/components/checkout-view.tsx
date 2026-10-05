'use client';

import { useEffect, useMemo, useRef, useState, useLayoutEffect } from 'react';
import { Minus, Plus, Warning } from '@phosphor-icons/react';
import { AnimatePresence } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { AmenitiesReminder, type ExtraPendiente } from '@/components/amenities-reminder';
import { BookingConfirmation } from '@/components/booking-confirmation';
import { CheckoutCalendar } from '@/components/checkout-calendar';
import { AyudaFlotante } from '@/components/checkout/ayuda-flotante';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { CamposContacto } from '@/components/checkout/campos-contacto';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { ItemPaso } from '@/components/checkout/item-paso';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { SelectPersonalizado } from '@/components/checkout/select-personalizado';
import { useAyudaContextual } from '@/components/checkout/use-ayuda-contextual';
import { useScrollAlFoco } from '@/components/checkout/use-scroll-al-foco';
import { DateField } from '@/components/date-field';
import { BloqueDePaso, CheckoutSectionCard } from '@/components/checkout-section-card';
import { CLASES_CAMPO_CON_ERROR, ErrorDeCampo } from '@/components/field-error';
import { PeopleStepper } from '@/components/people-stepper';
import { FormularioPago, NotaSeguridadStripe, StripePanel } from '@/components/stripe-panel';
import { TimeField } from '@/components/time-field';
import { useToast } from '@/components/toast';
import { WaitNotice } from '@/components/wait-notice';
import {
  ApiError,
  crearPago,
  getCupo,
  getEstadoReserva,
  guardarReserva,
  validarCodigoPromocional,
  type EstadoReservaPagada,
  type Moneda,
  type Pago,
  type ServicioCatalogo,
} from '@/lib/api';
import { formatHour, fromLocalISODate, MAX_PEOPLE, toLocalISODate } from '@/lib/dates';
import { horasDeServicio } from '@/lib/horario-servicio';
import { mensajeDeAyuda, mensajeDeError } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import {
  cantidadEfectiva,
  erroresPersonalizaciones,
  seleccionInicial,
  separarPersonalizaciones,
  totalPersonalizaciones,
  type SeleccionPersonalizacion,
} from '@/lib/personalizaciones';
import {
  estadoDeTarjeta, estadoVisible, numeroDePaso, unidaConAnterior, type EstadoTarjeta, type EstadoVisible, type PasoId,
} from '@/lib/pasos-checkout';
import { leerRef } from '@/lib/ref';
import { borrarPendiente, guardarPendiente } from '@/lib/pendientes';

// Mismas reglas que el backend (apps/bookings/validators.py). Aqui existen para
// que el cliente vea el error antes de llegar a la pantalla de pago, no para
// sustituir la validacion del servidor — esta se salta con un curl.
const DIGITOS_TELEFONO_MIN = 10;
const DIGITOS_TELEFONO_MAX = 15;

function telefonoValido(valor: string) {
  if (!/^[\d\s+()\-.]+$/.test(valor.trim())) return false;
  const digitos = valor.replace(/\D/g, '').length;
  return digitos >= DIGITOS_TELEFONO_MIN && digitos <= DIGITOS_TELEFONO_MAX;
}

// Deliberadamente permisivo: acentos, apostrofos y guiones son parte de nombres
// reales. Solo se rechaza lo que claramente no es un nombre.
function nombreValido(valor: string) {
  return !/\d/.test(valor) && /\p{L}/u.test(valor);
}

// No se intenta replicar el RFC del correo: el backend tiene la ultima palabra
// (`EmailField`). Esto solo caza los errores de dedo obvios.
function correoValido(valor: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor.trim());
}

// Los montos que manda el backend son texto con dos decimales (Decimal, ver
// `Reserva.precio_total`/`monto_pagado`) justo para no pasar por el float de
// JS. Restarlos como Number a secas reintroduce ese mismo riesgo un paso
// despues — redondear a centavos antes de restar es lo mismo que ya hace el
// servidor (`a_centavos` en apps/payments/pricing.py) para el mismo problema.
function centavosDe(monto: string) {
  return Math.round(Number(monto) * 100);
}

const CLAVE_CHECKOUT_ID = 'salysol:checkout-id';

/**
 * Identificador de esta sesion de checkout. Vive en sessionStorage para que
 * sobreviva a una recarga: el backend lo usa como llave y reescribe la misma
 * reserva en vez de dejar una fila nueva por cada intento.
 *
 * `recuperable` dice si este id ya existia en sessionStorage antes de este
 * montaje — o sea, si vale la pena preguntarle al backend por una reserva
 * asociada (ver el efecto de recuperacion mas abajo). Una pestana nueva
 * siempre genera un id nuevo y `recuperable` sale en `false`: no hay nada que
 * buscar y no tiene sentido gastar la peticion.
 *
 * NOTA: sessionStorage se lee en un useLayoutEffect para evitar el mismatch de
 * hidratacion. El useState initializer corre tanto en SSR como en el cliente; si
 * accede a sessionStorage ahi, el servidor devuelve {id:'',recuperable:false} y
 * el cliente encuentra un id guardado y devuelve otro valor — React lo detecta
 * como mismatch y tumba el arbol entero. Al arrancar con null en ambos lados y
 * leer sessionStorage despues del montaje, SSR y cliente parten del mismo punto.
 */
function useCheckoutId() {
  // null = aun no se ha leido sessionStorage (estado transitorio solo del cliente
  // antes del primer paint). Se resuelve en el useLayoutEffect de abajo.
  const [value, setValue] = useState<{ id: string; recuperable: boolean } | null>(null);

  // useLayoutEffect corre antes del primer paint visible: el componente padre
  // puede leer `recuperable` antes de renderizar la pantalla de carga inicial,
  // igual que antes. No se usa useEffect (que corre despues del paint) para
  // evitar un flash de la pantalla equivocada en reconexiones.
  /* eslint-disable react-hooks/set-state-in-effect -- lectura unica de sessionStorage,
     que no existe en el servidor; no hay forma de resolverla durante el render sin
     romper la hidratacion (ver nota arriba). */
  useLayoutEffect(() => {
    const guardado = window.sessionStorage.getItem(CLAVE_CHECKOUT_ID);
    if (guardado) {
      setValue({ id: guardado, recuperable: true });
      return;
    }
    const nuevo = crypto.randomUUID();
    window.sessionStorage.setItem(CLAVE_CHECKOUT_ID, nuevo);
    setValue({ id: nuevo, recuperable: false });
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  return value;
}

type CheckoutViewProps = {
  lang: Locale;
  dict: Dictionary;
  initialDay: string;
  initialTime: string;
  initialPeople: number;
  minDate: string;
  // `true` si day/time/people vinieron explicitos en la URL: el cliente acaba
  // de elegir viaje en el booking bar, no recargo esta pagina. Ver el efecto
  // de recuperacion mas abajo.
  queryOverride: boolean;
  empresaSlug?: string;
  servicioId?: number | string | null;
  servicioNombre?: string | null;
  servicio?: ServicioCatalogo | null;
};

// 'recuperando': solo se pasa por aqui si esta pestana ya tenia un checkout_id
// guardado (ver useCheckoutId) — se pregunta si tiene una reserva detras antes
// de decidir si el checkout arranca vacio, precargado, o directo en la
// confirmacion.
type Phase = 'recuperando' | 'form' | 'submitting' | 'payment' | 'confirmed' | 'unavailable' | 'error';

type CampoContacto = 'fullName' | 'phone' | 'email';

/**
 * Orden en que se busca el primer campo malo para mandarle el foco. Es el orden
 * visual del formulario, no el de validacion: mandar el foco a un campo que esta
 * mas arriba de otro que tambien fallo desorienta.
 */
const ORDEN_CAMPOS: CampoContacto[] = ['phone', 'fullName', 'email'];

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

export function CheckoutView({
  lang,
  dict,
  initialDay,
  initialTime,
  initialPeople,
  minDate,
  queryOverride,
  empresaSlug,
  servicioId,
  servicioNombre,
  servicio,
}: CheckoutViewProps) {
  const { checkout, booking } = dict;
  // null mientras sessionStorage todavia no se ha leido (solo dura hasta el
  // primer useLayoutEffect del cliente — ver useCheckoutId).
  const checkoutIdValue = useCheckoutId();
  const checkoutId = checkoutIdValue?.id ?? '';
  const recuperable = checkoutIdValue?.recuperable ?? false;
  const catalogoUnificado = servicio?.personalizaciones ?? [];
  const pideHora = servicio ? servicio.pide_hora : true;
  const horasDisponibles = servicio ? horasDeServicio(servicio) : [];

  const [day, setDay] = useState(initialDay);
  const [time, setTime] = useState(initialTime);
  const [people, setPeople] = useState(initialPeople);
  const [personalizaciones, setPersonalizaciones] = useState<SeleccionPersonalizacion[]>(() =>
    seleccionInicial(catalogoUnificado).map((seleccion) => {
      const item = catalogoUnificado.find((p) => p.id === seleccion.id);
      return {
        ...seleccion,
        cantidad: item?.cantidad_editable ? initialPeople : seleccion.cantidad,
      };
    }),
  );
  const [fechaSalidaManual, setFechaSalidaManual] = useState<string | null>(null);
  const defaultFechaSalida = useMemo(() => {
    const d = fromLocalISODate(day);
    d.setDate(d.getDate() + 1);
    return toLocalISODate(d);
  }, [day]);
  const fechaSalida = fechaSalidaManual && fechaSalidaManual > day ? fechaSalidaManual : defaultFechaSalida;

  const tieneHospedaje = servicio?.estrategia_cupo === 'por_noche';

  const personalizacionesMap = useMemo(() => {
    return new Map(personalizaciones.map((p) => [p.id, p]));
  }, [personalizaciones]);

  const alternarPersonalizacion = (id: number, checked: boolean) => {
    const item = catalogoUnificado.find((p) => p.id === id);
    setPersonalizaciones((prev) =>
      checked
        ? [
            ...prev.filter((p) => p.id !== id),
            { id, cantidad: item?.cantidad_editable ? people : 1 },
          ]
        : prev.filter((p) => p.id !== id),
    );
  };

  const actualizarRespuestaPersonalizacion = (id: number, respuesta: string) => {
    setPersonalizaciones((prev) => [
      ...prev.filter((p) => p.id !== id),
      { id, cantidad: 1, respuesta },
    ]);
    setErroresPersonalizacion((prev) => {
      if (!(id in prev)) return prev;
      const siguiente = { ...prev };
      delete siguiente[id];
      return siguiente;
    });
  };

  const ajustarCantidadPersonalizacion = (id: number, delta: number) => {
    setPersonalizaciones((prev) =>
      prev.map((seleccion) =>
        seleccion.id === id
          ? {
              ...seleccion,
              cantidad: Math.min(people, Math.max(1, (seleccion.cantidad ?? people) + delta)),
            }
          : seleccion,
      ),
    );
  };

  const cambiarPersonas = (cantidad: number) => {
    setPeople(cantidad);
    setPersonalizaciones((prev) =>
      prev.map((seleccion) => {
        const item = catalogoUnificado.find((p) => p.id === seleccion.id);
        return item?.cantidad_editable
          ? { ...seleccion, cantidad: Math.min(seleccion.cantidad ?? cantidad, cantidad) }
          : seleccion;
      }),
    );
  };
  // Numero de la reserva, para la pantalla de confirmacion (folio, recibo,
  // mensaje de WhatsApp). Se conoce en cuanto se guarda la reserva, antes de
  // que el pago pase.
  const [reservaId, setReservaId] = useState<number | null>(null);
  // Precarga segun el idioma del sitio (en -> USD, es -> MXN): el cliente que
  // llega en ingles es sobre todo turismo de EEUU/Canada y hoy tenia que darle
  // clic al selector en cada checkout para corregir un default que casi nunca
  // le servia. El selector se queda visible y editable — esto solo cambia la
  // primera respuesta, nunca decide por el cliente sin dejarlo ver ni tocar.
  //
  // El tipo de cambio de la sede habilita el selector USD.
  const [moneda, setMoneda] = useState<Moneda>(() => {
    if (lang !== 'en') return 'MXN';
    if (servicio) return Number(servicio.tipo_cambio_usd) > 0 ? 'USD' : 'MXN';
    return 'MXN';
  });
  const [formaPago, setFormaPago] = useState<'completo' | 'anticipo'>('completo');
  const permiteAnticipo = servicio?.permite_anticipo ?? true;
  const formaPagoEfectiva = permiteAnticipo ? formaPago : 'completo';
  const { mostrar: avisar } = useToast();

  const [contact, setContact] = useState({ phone: '', fullName: '', email: '' });

  // Para poder mandarle el foco al primer campo con error.
  const refPhone = useRef<HTMLInputElement>(null);
  const refFullName = useRef<HTMLInputElement>(null);
  const refEmail = useRef<HTMLInputElement>(null);
  const refStripePanel = useRef<HTMLDivElement>(null);
  const refsContacto: Record<CampoContacto, React.RefObject<HTMLInputElement | null>> = {
    phone: refPhone,
    fullName: refFullName,
    email: refEmail,
  };
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  // Antes esto usaba el `ErrorBlock` grande (icono + boton de WhatsApp) del
  // mecanismo generico de `phase === 'error'`, pensado para fallos de red o
  // de pago que el cliente no puede resolver solo. Olvidarse de una casilla
  // si puede resolverlo solo, y el bloque completo empujaba el boton de pagar
  // hacia abajo. Mismo patron liviano que ya usan telefono/nombre/correo:
  // texto rojo pegado al campo, sin abrir un bloque nuevo.
  const [errorWaiver, setErrorWaiver] = useState(false);
  // La fase inicial se decide en el useLayoutEffect de abajo, una vez que
  // checkoutIdValue esta disponible. Antes de eso se usa 'recuperando' como
  // pantalla de espera neutral — muestra el spinner de "buscando tu reserva"
  // sin comprometer nada hasta saber si hay sessionStorage que recuperar.
  const [phase, setPhase] = useState<Phase>('recuperando');
  useEffect(() => {
    if (phase === 'confirmed' && checkoutId) borrarPendiente(checkoutId);
  }, [phase, checkoutId]);
  const phaseInicializada = useRef(false);
  const tieneProducto = Boolean(servicio);
  useLayoutEffect(() => {
    // Solo se ejecuta una vez, cuando checkoutIdValue pasa de null a un valor
    // real. A partir de ahi la logica de recuperacion toma el control.
    if (checkoutIdValue === null || phaseInicializada.current) return;
    phaseInicializada.current = true;
    setPhase(recuperable ? 'recuperando' : tieneProducto ? 'form' : 'unavailable');
  }, [checkoutIdValue, recuperable, tieneProducto]);
  const [error, setError] = useState('');
  // Monto real cobrado, cuando la confirmacion viene de una reserva recuperada
  // (ver el efecto de abajo) en vez de un pago recien hecho en esta misma
  // visita. `null` = mostrar lo que ya calcula el resto del checkout
  // (`amountDueNow`/`total`), que es lo correcto para un pago fresco: la
  // reserva recuperada puede llevar otro precio o amenidades que ya no estan
  // en el estado local, asi que aqui se confia lo que de verdad se cobro y no
  // lo que el precio de hoy recalcularia.
  const [recuperadoPagado, setRecuperadoPagado] = useState<number | null>(null);
  const [recuperadoSaldo, setRecuperadoSaldo] = useState<number | null>(null);
  // Desglose de personalizaciones ya congelado al pagar, para una reserva
  // recuperada. Se guarda crudo (no formateado) porque `currency` depende de
  // `moneda`, y `moneda` recien se esta fijando en el mismo efecto que llena
  // esto — el formateo real ocurre despues, al construir `lineasExtrasRecuperadas`.
  const [recuperadoPersonalizaciones, setRecuperadoPersonalizaciones] = useState<
    EstadoReservaPagada['personalizaciones']
  >([]);
  const [recuperadoCodigoPromocional, setRecuperadoCodigoPromocional] = useState<string | null>(null);
  const [recuperadoDescuento, setRecuperadoDescuento] = useState<number | null>(null);
  const [pago, setPago] = useState<Pago | null>(null);
  const [codigoPromocional, setCodigoPromocional] = useState('');
  const [promoEstado, setPromoEstado] = useState<'idle' | 'verificando' | 'valido' | 'invalido'>(
    'idle',
  );
  const [promoPorcentaje, setPromoPorcentaje] = useState<string | null>(null);
  const [recordatorioAbierto, setRecordatorioAbierto] = useState(false);
  const [pagoProcesando, setPagoProcesando] = useState(false);
  // Dia sin lugar para este grupo, con la alternativa que ofrece el backend.
  // **No se reasigna la fecha sola.** Antes se hacia (`setDay(proxima)`) y el
  // campo cambiaba bajo las manos del cliente despues de que el ya habia
  // elegido: rompe la expectativa universal de que tocar un dia lo selecciona, y
  // el peor caso era llegar desde la portada, donde el salto ocurria durante el
  // primer pintado. Ahora los dias llenos van en gris en el calendario y esto
  // solo cubre el caso que el gris no alcanza a atajar: llegar por URL con una
  // fecha que ya no sirve, o que se llene mientras el cliente llena el formulario.
  const [sinLugar, setSinLugar] = useState<{ mensaje: string; alternativa: string | null } | null>(
    null,
  );
  const cupoCheckId = useRef(0);

  // Depende de `people` ademas de `day`: un dia puede tener lugares libres y aun
  // asi no recibir a un grupo de 4, porque solo dos pangas de la flota lo llevan.
  useEffect(() => {
    const checkId = ++cupoCheckId.current;

    (async () => {
      let cupo;
      try {
        cupo = await getCupo(day, people, empresaSlug);
      } catch {
        // Sin respuesta no se avisa nada: es ayuda adelantada, el cupo real lo
        // valida el backend al cobrar. Nunca debe trabar el checkout.
        return;
      }
      if (cupoCheckId.current !== checkId) return;

      if (cupo.disponible) {
        setSinLugar(null);
        return;
      }

      // Dos mensajes distintos porque son dos problemas distintos: al cliente de
      // 4 personas hay que decirle que el dia si tiene espacio pero no para su
      // grupo — si no, ve lugares libres y no entiende por que no puede.
      const plantilla =
        cupo.motivo_no_disponible === 'sin_panga' || cupo.motivo_no_disponible === 'sin_lugar'
          ? checkout.noBoatForGroupNotice
          : checkout.dayFullOffer;

      setSinLugar({
        mensaje: plantilla
          .replace('{date}', formatDay(fromLocalISODate(day), lang))
          .replace('{people}', String(people)),
        alternativa: cupo.proxima_disponible,
      });
    })();
  }, [day, people, lang, checkout.dayFullOffer, checkout.noBoatForGroupNotice, empresaSlug]);

  const promoCheckId = useRef(0);

  // El estado deriva del tecleo mismo (idle/verificando), aqui en el handler y
  // no en el efecto de abajo: poner un setState sincrono en el cuerpo de un
  // efecto dispara un render en cascada. El efecto solo hace lo que si
  // necesita esperar — la llamada de red con debounce.
  const onCodigoPromocionalChange = (value: string) => {
    setCodigoPromocional(value);
    setPromoEstado(value.trim() ? 'verificando' : 'idle');
    if (!value.trim()) setPromoPorcentaje(null);
  };

  // Con debounce (no en cada tecla): a diferencia de `getCupo`, este si depende
  // de texto libre. La respuesta es solo informativa — `crear-pago` vuelve a
  // validar el codigo con el subtotal real (ver apps/payments/views.py) — asi
  // que un fallo de red aqui no debe bloquear nada, solo deja el campo sin
  // confirmar.
  useEffect(() => {
    const codigo = codigoPromocional.trim();
    if (!codigo) return;

    const checkId = ++promoCheckId.current;

    const timer = setTimeout(async () => {
      let resultado;
      try {
        resultado = await validarCodigoPromocional(codigo, contact.email, empresaSlug);
      } catch {
        if (promoCheckId.current === checkId) setPromoEstado('idle');
        return;
      }
      if (promoCheckId.current !== checkId) return;

      if (resultado.valido) {
        setPromoEstado('valido');
        setPromoPorcentaje(resultado.porcentaje_descuento);
      } else {
        setPromoEstado('invalido');
        setPromoPorcentaje(null);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [codigoPromocional, contact.email, empresaSlug]);

  const usdDisponible = Number(servicio?.tipo_cambio_usd) > 0;
  const tourPrice = servicio
    ? aMoneda(servicio.precio_base, moneda, servicio.tipo_cambio_usd)
    : null;

  const currency = useMemo(
    () => new Intl.NumberFormat(intlLocale(lang), { style: 'currency', currency: moneda }),
    [lang, moneda],
  );

  // "2 de 5": leyenda para el extra con cantidad editable para decir la cantidad elegida.
  const deLabel = (cantidad: number, total: number) =>
    checkout.cantidadDeLabel.replace('{cantidad}', String(cantidad)).replace('{total}', String(total));

  /**
   * Todo lo del catalogo que el cliente NO lleva: es lo que el recordatorio
   * de antes de pagar puede ofrecerle.
   *
   * Cuenta cualquier item sin marcar, no solo los recomendados. Filtrarlo a
   * `preseleccionado` dejaba el recordatorio muerto desde que los
   * recomendados empezaron a venir marcados —la lista salia siempre vacia— y
   * de paso nunca ofrecia el brunch, que es el unico que no viene marcado y
   * por lo tanto el unico que de verdad hacia falta ofrecer.
   *
   * Los precios se convierten con el tipo de cambio de la sede.
   */
  const personalizacionesPendientes: ExtraPendiente[] = catalogoUnificado
    .filter(
      (p) =>
        p.tipo_interaccion === 'check' &&
        p.preseleccionado &&
        !personalizacionesMap.has(p.id),
    )
    .map((p) => {
      const precio = aMoneda(p.precio, moneda, servicio?.tipo_cambio_usd);
      return {
        id: p.id,
        avisoReforzado: p.aviso_reforzado,
        nombre: p.nombre,
        monto:
          precio === null
            ? null
            : currency.format(
                precio * cantidadEfectiva(p, people, people),
              ),
        hint: null,
      };
    });
  const opcionesPendientes = personalizacionesPendientes;

  // El precio es por viaje (la reserva es de la embarcacion completa), pero
  // pasando de las personas incluidas se suma un cargo por cada una. El servidor
  // recalcula esto mismo al crear el pago: aqui solo se muestra.
  const personasIncluidas = servicio?.personas_incluidas ?? 0;
  const precioPersonaExtra = servicio
    ? aMoneda(servicio.precio_persona_extra, moneda, servicio.tipo_cambio_usd) ?? 0
    : 0;
  const personasExtra = Math.max(0, people - personasIncluidas);
  const cargoPersonas = personasExtra * (precioPersonaExtra || 0);

  const cargoPersonalizacionesServicio = totalPersonalizaciones(
    catalogoUnificado, personalizaciones, people, moneda, servicio?.tipo_cambio_usd ?? '',
  );

  const subtotalSinDescuento = tourPrice === null || cargoPersonalizacionesServicio === null
    ? null
    : tourPrice + cargoPersonas + cargoPersonalizacionesServicio;

  // Solo informativo (redondeo igual al de `cargo_por_descuento` en
  // apps/payments/pricing.py): el monto real lo congela `crear-pago` sobre el
  // subtotal exacto, este puede diferir por centavos de redondeo.
  const descuentoPromocional =
    subtotalSinDescuento !== null && promoEstado === 'valido' && promoPorcentaje
      ? Math.min(
          subtotalSinDescuento,
          Math.round(subtotalSinDescuento * (Number(promoPorcentaje) / 100) * 100) / 100,
        )
      : 0;

  /**
   * Las lineas de lo que se compro aparte del viaje (mas el descuento, si
   * aplica). Se arman una sola vez y las usan los dos lugares que las
   * enseñan — el resumen de pago y el ticket de la confirmacion — para que
   * no puedan decir cosas distintas.
   */
  const lineasExtras = [
    ...catalogoUnificado
      .filter((p) => p.tipo_interaccion === 'check' && personalizacionesMap.has(p.id))
      .map((p) => {
        const seleccion = personalizacionesMap.get(p.id);
        const precioCrudo = aMoneda(p.precio, moneda, servicio?.tipo_cambio_usd);
        const cantidad = cantidadEfectiva(p, people, seleccion?.cantidad);
        return {
          label: cantidad > 1 ? `${p.nombre} (${cantidad})` : p.nombre,
          amount:
            precioCrudo === null
              ? checkout.extrasUnavailableInCurrency
              : currency.format(precioCrudo * cantidad),
        };
      }),
    ...(descuentoPromocional > 0
      ? [
          {
            label: `${checkout.promoCode.discountLabel} (${codigoPromocional.trim().toUpperCase()})`,
            amount: `-${currency.format(descuentoPromocional)}`,
          },
        ]
      : []),
  ];

  /**
   * Mismo formato que `lineasExtras`, pero a partir del desglose ya congelado
   * que trae una reserva recuperada (ver `EstadoReservaPagada`) — no del
   * catalogo vigente, que puede haber cambiado de precio desde entonces. El
   * descuento tambien viene ya congelado: el % vigente del codigo hoy podria
   * ser otro.
   */
  const lineasExtrasRecuperadas = [
    ...recuperadoPersonalizaciones
      .filter((p) => p.tipo_interaccion === 'check' && p.monto !== null)
      .map((p) => ({
        label: p.cantidad > 1 ? `${p.nombre} (${p.cantidad})` : p.nombre,
        amount: currency.format(Number(p.monto)),
      })),
    ...(recuperadoDescuento !== null
      ? [
          {
            label: `${checkout.promoCode.discountLabel} (${recuperadoCodigoPromocional})`,
            amount: `-${currency.format(recuperadoDescuento)}`,
          },
        ]
      : []),
  ];

  const lines = tourPrice === null
    ? []
    : [
        { label: servicio?.nombre || checkout.tourLabel, amount: currency.format(tourPrice) },
        ...(cargoPersonas > 0
          ? [
              {
                label: `${checkout.extraPeopleLabel} (${personasExtra} × ${currency.format(precioPersonaExtra)})`,
                amount: currency.format(cargoPersonas),
              },
            ]
          : []),
        ...lineasExtras,
      ];

  const total = subtotalSinDescuento === null ? null : subtotalSinDescuento - descuentoPromocional;
  const amountDueNow =
    total === null
      ? null
      : formaPagoEfectiva === 'anticipo' && servicio
        ? Math.round(total * (servicio.porcentaje_anticipo / 100) * 100) / 100
        : total;

  const dayDate = useMemo(() => fromLocalISODate(day), [day]);

  /** Que campo esta mal y por que. Vacio = ninguno. */
  const [erroresCampo, setErroresCampo] = useState<Partial<Record<CampoContacto, string>>>({});
  const [erroresPersonalizacion, setErroresPersonalizacion] = useState<Record<number, string>>({});

  // Paso en el que va el cliente (viaje → contacto → detalles → pago) y cuál ya
  // contestado reabrió a mano con "Modificar". Día/hora/personas llegan
  // precargados desde la barra de reserva, así que el primer paso no tiene un
  // momento natural de "ya se llenó": necesita un click explícito para avanzar.
  const [actual, setActual] = useState<PasoId>('viaje');
  const [editando, setEditando] = useState<PasoId | null>(null);
  const ayuda = useAyudaContextual();
  // Al cambiar de paso, la tarjeta en foco se trae a la vista solo si hace falta.
  useScrollAlFoco(`${actual}|${editando}|${phase === 'payment'}`);

  /**
   * Repone el checkout de esta pestana, si `checkoutId` ya traia una reserva
   * detras (ver `useCheckoutId`).
   *
   * Antes, recargar a media compra dejaba el formulario en blanco: si el pago
   * ya habia pasado, el cliente se topaba con un 409 sin ninguna forma de ver
   * su confirmacion; si seguia sin pagar, tenia que volver a escribir todo.
   * Un `checkout_id` ajeno no sirve de nada aqui — es un UUID al azar que solo
   * conoce el navegador que lo genero (mismo principio que ya usa
   * `crear-pago`) — asi que no hace falta ninguna otra verificacion antes de
   * mostrar lo que el backend responda.
   *
   * Corre una sola vez al montar: `checkoutId` y `recuperable` no cambian
   * durante la vida del componente.
   */
  useEffect(() => {
    // Espera a que useLayoutEffect resuelva sessionStorage antes de decidir
    // si hay algo que recuperar. Sin esta guarda, el efecto corria con
    // recuperable=false (el default de null) y dejaba phase en 'recuperando'
    // para siempre.
    if (checkoutIdValue === null) return;
    if (!recuperable) return;
    let cancelado = false;

    (async () => {
      let estado;
      try {
        estado = await getEstadoReserva(checkoutId, empresaSlug);
      } catch {
        // 404 (nada que recuperar), sin red, lo que sea: seguir como si esta
        // pestana no tuviera nada guardado. Nunca debe trabar el checkout.
        if (!cancelado) {
          setPhase(tieneProducto ? 'form' : 'unavailable');
        }
        return;
      }
      if (cancelado) return;

      if (estado.estado === 'pagada') {
        setReservaId(estado.reserva_id);
        setDay(estado.fecha);
        setTime(estado.hora ?? '');
        setPeople(estado.numero_personas);
        setContact((c) => ({ ...c, fullName: estado.nombre_cliente, email: estado.correo_cliente }));
        setMoneda(estado.moneda);
        setRecuperadoPagado(estado.monto_pagado !== null ? Number(estado.monto_pagado) : null);
        setRecuperadoSaldo(
          estado.forma_pago === 'anticipo' &&
            estado.precio_total !== null &&
            estado.monto_pagado !== null
            ? (centavosDe(estado.precio_total) - centavosDe(estado.monto_pagado)) / 100
            : null,
        );
        setRecuperadoPersonalizaciones(estado.personalizaciones);
        setRecuperadoCodigoPromocional(estado.codigo_promocional);
        setRecuperadoDescuento(
          estado.descuento_aplicado !== null ? Number(estado.descuento_aplicado) : null,
        );
        setPhase('confirmed');
        return;
      }

      if (estado.estado === 'pendiente_pago') {
        // Repone el formulario completo, deslinde aparte: es una constancia
        // legal por envio y no se puede dar por aceptada de una vez anterior.
        setReservaId(estado.reserva_id);
        // Salvo viaje: si la URL ya trajo day/time/people explicitos, el
        // cliente acaba de elegir en el booking bar y esa eleccion gana sobre
        // la reserva vieja sin pagar que sigue en esta pestana. Sin este
        // guard, un checkout abandonado a medias (nunca llega a 'confirmed',
        // asi que su checkout_id nunca se borra) pisaba en silencio la fecha
        // recien elegida con la vieja cada vez que se reusaba la pestana.
        if (!queryOverride) {
          setDay(estado.fecha);
          setTime(estado.hora ?? '');
          setPeople(estado.numero_personas);
        }
        setContact({
          fullName: estado.nombre_cliente,
          phone: estado.telefono_cliente,
          email: estado.correo_cliente,
        });
        setMoneda(estado.moneda);
        // Un arreglo vacío también es una decisión restaurada: no aplicar de
        // nuevo los checks recomendados después de una recarga.
        setPersonalizaciones(estado.personalizaciones);
        if (estado.forma_pago) setFormaPago(estado.forma_pago);
        setActual('pago');
        setPhase(tieneProducto ? 'form' : 'unavailable');
        return;
      }

      // 'cancelada': nada que reponer — esta reserva ya no sirve. Se sigue con
      // el formulario vacio normal, como si no hubiera nada guardado.
      setPhase(tieneProducto ? 'form' : 'unavailable');
    })();

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkoutIdValue]);

  /**
   * Borra el `checkout_id` de esta pestana al salir de la confirmacion — pero
   * solo si se sale navegando, nunca si se sale recargando la pagina.
   *
   * Sin esto, un cliente que paga y le da a "Reservar" otra vez EN LA MISMA
   * PESTANA (sin cerrarla ni recargar) se encontraria de nuevo con la
   * confirmacion del viaje que ya pago: el efecto de recuperacion de arriba
   * sigue viendo el mismo `checkout_id` y esa reserva sigue siendo la mas
   * reciente. Una vez que el cliente ya vio su folio, ese `checkout_id` dejo de
   * servir para nada mas que repetirle lo mismo.
   *
   * La distincion entre "recargar" y "navegar" no hay que inventarla: un
   * recargo destruye el runtime de React entero, asi que este cleanup nunca
   * llega a correr y el `checkout_id` sobrevive — reponer la MISMA confirmacion
   * tras un recargo (el caso que motivo todo esto) sigue funcionando igual.
   * Una navegacion de Next (el link "Volver al inicio", el boton atras) si
   * desmonta el componente en el propio React, y ahi es donde este cleanup
   * corre y limpia la llave antes de que el cliente pueda volver a usarla.
   */
  const phaseRef = useRef(phase);
  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    return () => {
      if (phaseRef.current === 'confirmed') {
        window.sessionStorage.removeItem(CLAVE_CHECKOUT_ID);
      }
    };
  }, []);

  /**
   * Valida los datos de contacto y devuelve los errores por campo.
   *
   * Antes esto ponia un solo mensaje generico al pie del panel de pago, asi que
   * el cliente sabia que algo estaba mal pero tenia que ponerse a buscar cual:
   * una tarea de busqueda encima de una tarea de formulario. Ahora cada mensaje
   * viaja pegado a su campo.
   */
  const validarContacto = (): Partial<Record<CampoContacto, string>> => {
    const errores: Partial<Record<CampoContacto, string>> = {};

    if (!contact.fullName.trim()) errores.fullName = checkout.missingFields;
    else if (!nombreValido(contact.fullName)) errores.fullName = checkout.invalidName;

    if (!contact.phone.trim()) errores.phone = checkout.missingFields;
    else if (!telefonoValido(contact.phone)) errores.phone = checkout.invalidPhone;

    if (!contact.email.trim()) errores.email = checkout.missingFields;
    else if (!correoValido(contact.email)) errores.email = checkout.invalidEmail;

    return errores;
  };

  /**
   * Boton "Confirmar" del paso 2 — igual que el del paso 1, un clic explicito
   * en vez de avanzar solo al salir del ultimo campo. Antes avanzaba en el
   * `onBlur`, pero eso mezclaba dos señales distintas (dejar el campo,
   * terminar el paso) en un mismo gesto, y no se replica en el paso 3 (una
   * casilla no tiene "salir del campo" que valga como confirmacion).
   */
  const confirmarContacto = () => {
    const errores = validarContacto();
    setErroresCampo(errores);

    if (Object.keys(errores).length > 0) {
      ayuda.tropezar('validacion');
      const primero = ORDEN_CAMPOS.find((campo) => errores[campo]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }

    setActual((a) => (a === 'contacto' ? 'detalles' : a));
    setEditando(null);
  };

  const confirmarViaje = () => {
    setActual((a) => (a === 'viaje' ? 'contacto' : a));
    setEditando(null);
  };

  /** Extras confirmados: pasa al pago y lo trae a la vista (en móvil el panel de pago aparece aquí). */
  const continuarAPago = () => {
    setActual('pago');
    setEditando(null);
    setTimeout(() => {
      refStripePanel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  };

  /** Primer paso del pago: valida, y antes de tocar la red ofrece las amenidades. */
  const iniciarPago = () => {
    const errores = validarContacto();
    setErroresCampo(errores);

    if (Object.keys(errores).length > 0) {
      ayuda.tropezar('validacion');
      // El foco salta al primer campo malo. Sin esto, quien navega con teclado o
      // con lector de pantalla no tiene forma de enterarse de que hay un error:
      // el mensaje existe visualmente y para el nadie lo dijo.
      const primero = ORDEN_CAMPOS.find((campo) => errores[campo]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }

    // Sin deslinde aceptado no hay reserva; el backend lo rechaza igual.
    if (!waiverAccepted) {
      ayuda.tropezar('validacion');
      setErrorWaiver(true);
      return;
    }

    if (total === null || amountDueNow === null) {
      return;
    }

    const erroresDePersonalizacion = erroresPersonalizaciones(catalogoUnificado, personalizaciones);
    setErroresPersonalizacion(erroresDePersonalizacion);
    const primeraPersonalizacion = catalogoUnificado.find(
      (p) => erroresDePersonalizacion[p.id],
    );
    if (primeraPersonalizacion) {
      ayuda.tropezar('validacion');
      const campo = document.getElementById(`personalizacion-${primeraPersonalizacion.id}`);
      campo?.focus();
      campo?.scrollIntoView({ block: 'center' });
      return;
    }

    if (opcionesPendientes.length > 0) {
      setRecordatorioAbierto(true);
      return;
    }

    enviar();
  };

  /**
   * Unico punto que toca la red. Se protege contra envios repetidos con la
   * fase: mientras esta en `submitting` no vuelve a entrar, y la reserva se
   * guarda con `checkout_id`, asi que reintentar tras un error reescribe la
   * misma fila en vez de crear otra.
   */
  const enviar = async () => {
    if (phase === 'submitting' || phase === 'payment') return;

    setPhase('submitting');
    setError('');

    try {
      const reserva = await guardarReserva({
        checkout_id: checkoutId,
        fecha: day,
        ...(pideHora ? { hora: time } : {}),
        numero_personas: people,
        nombre_cliente: contact.fullName,
        telefono_cliente: contact.phone,
        correo_cliente: contact.email,
        moneda,
        deslinde_aceptado: waiverAccepted,
        // El nombre del deslinde es el que el cliente ya escribio en sus datos:
        // pedirlo dos veces no aporta nada y estorba el checkout.
        deslinde_nombre: contact.fullName.trim(),
        // A quien le cuenta la venta, si el cliente llego por el link de alguien.
        ref: leerRef(),
        captcha_token: captchaToken.current,
        servicio: servicio ? servicio.slug : (typeof servicioId === 'string' ? servicioId : undefined),
        // La seleccion viaja con la reserva, sin precio: crear-pago la congela
        // con el catalogo vigente al pagar (ver backend/apps/bookings/serializers.py).
        // Se manda siempre, incluido `[]`, para que reenviar el checkout borre
        // una seleccion vieja en vez de conservarla.
        personalizaciones: personalizaciones.map((seleccion) => {
          const item = catalogoUnificado.find((p) => p.id === seleccion.id);
          return {
            ...seleccion,
            cantidad: item
              ? cantidadEfectiva(item, people, seleccion.cantidad)
              : seleccion.cantidad,
          };
        }),
        fecha_salida: tieneHospedaje ? fechaSalida : undefined,
      }, empresaSlug);

      setReservaId(reserva.id);
      guardarPendiente({
        tipo: 'reserva', checkoutId,
        empresaSlug: empresaSlug ?? process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol',
        productoSlug: servicio?.slug ?? (typeof servicioId === 'string' ? servicioId : 'pesca-deportiva'),
        productoNombre: servicio?.nombre ?? servicioNombre ?? '',
        ruta: window.location.pathname + window.location.search,
        actualizadoEn: new Date().toISOString(),
      });

      const pagoResponse = await crearPago(reserva.id, {
        checkout_id: checkoutId,
        forma_pago: formaPagoEfectiva,
        // Solo si la validacion en vivo lo dio por bueno; `crear-pago` lo
        // vuelve a validar de todos modos con el subtotal real (ver
        // apps/payments/views.py, `_resolver_codigo_promocional`).
        codigo_promocional:
          promoEstado === 'valido' ? codigoPromocional.trim().toUpperCase() : undefined,
      }, empresaSlug);

      setPago(pagoResponse);
      setRecordatorioAbierto(false);
      setPhase('payment');
      // La reserva ya quedo guardada aunque el pago siga pendiente: decirlo
      // separa los dos pasos, para que un fallo de tarjeta no se lea como
      // "se perdio todo lo que llene".
      avisar('exito', dict.feedback.saved);
    } catch (err) {
      setRecordatorioAbierto(false);
      if (err instanceof ApiError && err.status === 503) {
        setPhase('unavailable');
        return;
      }
      // El codigo paso la validacion en vivo pero crear-pago lo rechazo con el
      // subtotal real (se agoto justo ahora, o vencio mientras el cliente
      // llenaba el formulario). Se marca invalido para que reintentar sin el
      // codigo funcione al primer intento, en vez de repetir el mismo 400.
      if (err instanceof ApiError && err.status === 400 && promoEstado === 'valido') {
        setPromoEstado('invalido');
        setError(checkout.promoCode.invalid);
        setPhase('error');
        return;
      }
      setError(mensajeDeError(err, checkout, dict.feedback));
      setPhase('error');
    }
  };

  const locked = phase === 'payment' || phase === 'unavailable';
  // Token de Turnstile. Lo produce el widget solo; el backend lo exige unicamente
  // al crear la reserva, asi que estar vacio no bloquea un reenvio.
  const captchaToken = useRef('');

  const enviando = phase === 'submitting';

  const personasResumen = `${people} ${people === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`;
  const horaTexto = pideHora && time ? formatHour(time) : '';
  const resumenPaso1 = [
    tieneHospedaje ? `${formatDay(dayDate, lang)} → ${formatDay(fromLocalISODate(fechaSalida), lang)}` : formatDay(dayDate, lang),
    horaTexto || null,
    personasResumen,
  ].filter(Boolean).join(' · ');
  const resumenPaso2 = `${contact.fullName} · ${contact.phone}`;

  // Lo que se le manda a la vendedora si el cliente usa la salida de emergencia
  // de un error. Lleva su fecha, hora y grupo para que ella no tenga que
  // preguntarlos y el no tenga que redactar nada ya estando frustrado.
  const ayudaMensaje = mensajeDeAyuda(pideHora ? dict.feedback.helpMessage : dict.feedback.helpMessageNoTime, {
    fecha: formatDay(dayDate, lang),
    hora: horaTexto,
    personas: people,
  });

  // Se pregunta antes de pintar nada del formulario: si esta reserva ya se
  // pago, no tiene sentido mostrar un instante el paso 1 vacio para luego
  // reemplazarlo por la confirmacion.
  if (phase === 'recuperando') {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-2 bg-surface px-6">
        <WaitNotice mensaje={dict.feedback.recoveringNotice} />
      </div>
    );
  }

  if (phase === 'confirmed') {
    return (
      <BookingConfirmation
        lang={lang}
        dict={dict}
        // No-null: esta fase solo se alcanza despues de crearPago (pago fresco)
        // o de recuperar una reserva ya pagada por su checkout_id — las dos
        // rutas ponen `reservaId` antes de llegar aqui.
        numeroDeConfirmacion={reservaId!}
        nombre={contact.fullName}
        email={contact.email}
        fecha={formatDay(dayDate, lang)}
        hora={horaTexto}
        personas={people}
        // Vacio en una reserva repuesta: `EstadoReservaView` solo devuelve el
        // monto cobrado en la rama `pagada`, no el desglose, y rearmarlo con
        // el catalogo de hoy podria enseñar un precio distinto del pagado.
        extras={recuperadoPagado !== null ? lineasExtrasRecuperadas : lineasExtras}
        // Un pago recuperado manda su propio monto (lo que Stripe cobro de
        // verdad): el precio de hoy o las amenidades en el estado local pueden
        // no ser ya las mismas con las que se pago.
        pagado={
          recuperadoPagado !== null
            ? currency.format(recuperadoPagado)
            : amountDueNow === null
              ? '—'
              : currency.format(amountDueNow)
        }
        saldoEnEfectivo={
          recuperadoPagado !== null
            ? recuperadoSaldo !== null && recuperadoSaldo > 0
              ? currency.format(recuperadoSaldo)
              : null
            : total !== null && amountDueNow !== null && total > amountDueNow
              ? currency.format(total - amountDueNow)
              : null
        }
        procesando={recuperadoPagado !== null ? false : pagoProcesando}
      />
    );
  }

  // Un solo foco abierto: si el cliente reabrió una respuesta, la tarjeta activa
  // se pliega a un renglón "pendiente" hasta que termine de corregirla.
  const hayEdicion = editando !== null;
  const estadoPaso = (id: PasoId): EstadoTarjeta | 'oculto' => {
    const estado = estadoDeTarjeta(id, actual, editando);
    // Con el pago en curso los extras ya no se pueden cambiar: reabrirlos no dejaría tocar nada.
    return estado !== 'oculto' && locked && id === 'detalles' ? 'completado' : estado;
  };
  const crudoViaje = estadoPaso('viaje') as EstadoTarjeta;
  const crudoContacto = estadoPaso('contacto');
  const crudoDetalles = estadoPaso('detalles');
  const estadoViaje = estadoVisible(crudoViaje, hayEdicion);
  const estadoContacto = crudoContacto === 'oculto' ? null : estadoVisible(crudoContacto, hayEdicion);
  const estadoDetalles = crudoDetalles === 'oculto' ? null : estadoVisible(crudoDetalles, hayEdicion);
  const secuencia: EstadoVisible[] = [estadoViaje];
  if (estadoContacto) secuencia.push(estadoContacto);
  if (estadoDetalles) secuencia.push(estadoDetalles);
  const reabrir = (id: PasoId) => setEditando((e) => (e === id ? null : id));
  const etiquetaAccion = (estado: EstadoTarjeta | 'oculto') =>
    estado === 'completado' ? checkout.changeStep : estado === 'editando' ? checkout.doneEditing : undefined;

  // El stepper cuenta el pago como paso 4 en cuanto se confirman los extras, o
  // antes si ya se mandó el formulario (en escritorio el panel siempre está a la vista).
  const pasoActualStepper = phase === 'submitting' || phase === 'payment' ? 4 : numeroDePaso(actual);
  const totalMovil = total !== null ? `${currency.format(total)} ${moneda}` : undefined;

  const lineasViaje = [
    { etiqueta: checkout.summary.date, valor: formatDay(dayDate, lang) },
    tieneHospedaje ? { etiqueta: checkout.summary.checkOut, valor: formatDay(fromLocalISODate(fechaSalida), lang) } : null,
    horaTexto ? { etiqueta: checkout.summary.time, valor: horaTexto } : null,
    { etiqueta: checkout.summary.people, valor: String(people) },
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);

  const renderPersonalizacion = (sp: (typeof catalogoUnificado)[number]) => {
                      const seleccion = personalizacionesMap.get(sp.id);
                      const marcada = Boolean(seleccion);
                      const errorCodigo = erroresPersonalizacion[sp.id] as
                        | 'required'
                        | 'number'
                        | 'selection'
                        | undefined;
                      const errorId = `error-personalizacion-${sp.id}`;
                      const precio = aMoneda(sp.precio, moneda, servicio?.tipo_cambio_usd);

                      if (sp.tipo_interaccion === 'check') {
                        const cantidad = cantidadEfectiva(sp, people, seleccion?.cantidad);
                        return (
                          <div key={sp.id}>
                            <label
                              htmlFor={`personalizacion-${sp.id}`}
                              className="flex items-start justify-between gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface"
                            >
                              <span className="flex items-start gap-3">
                                <input
                                  id={`personalizacion-${sp.id}`}
                                  type="checkbox"
                                  checked={marcada}
                                  disabled={locked}
                                  onChange={(e) => alternarPersonalizacion(sp.id, e.target.checked)}
                                  className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                                />
                                <span>
                                  <span className="font-medium">{sp.nombre}</span>
                                  {sp.preseleccionado && (
                                    <span className="ml-2 text-xs font-medium text-accent">
                                      {checkout.recommendedBadge}
                                    </span>
                                  )}
                                </span>
                              </span>
                              <span className="shrink-0 text-right text-muted">
                                {precio === null
                                  ? checkout.extrasUnavailableInCurrency
                                  : currency.format(Number(precio) * cantidad)}
                              </span>
                            </label>
                            {!marcada && sp.aviso_reforzado && (
                              <div className="flex items-start gap-2 border border-t-0 border-action/40 bg-action/10 px-4 py-2.5 text-xs text-foreground">
                                <Warning size={14} className="mt-0.5 shrink-0 text-action" />
                                <p>{checkout.amenitiesModal.reinforcedWarning}</p>
                              </div>
                            )}
                            {marcada && sp.cantidad_editable && people > 1 && (
                              <div className="flex items-center justify-between gap-3 border border-t-0 border-border bg-surface px-4 py-2.5 text-sm text-foreground">
                                <span className="text-muted">{checkout.licenseQuantity.question}</span>
                                <span className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => ajustarCantidadPersonalizacion(sp.id, -1)}
                                    disabled={locked || cantidad <= 1}
                                    aria-label="-"
                                    className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30"
                                  >
                                    <Minus size={12} />
                                  </button>
                                  <span>{deLabel(cantidad, people)}</span>
                                  <button
                                    type="button"
                                    onClick={() => ajustarCantidadPersonalizacion(sp.id, 1)}
                                    disabled={locked || cantidad >= people}
                                    aria-label="+"
                                    className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30"
                                  >
                                    <Plus size={12} />
                                  </button>
                                </span>
                              </div>
                            )}
                          </div>
                        );
                      }

                      const valor = seleccion?.respuesta ?? '';
                      if (sp.tipo_interaccion === 'input_seleccion') {
                        return (
                          <div key={sp.id} className="flex flex-col gap-2 text-sm text-foreground">
                            <SelectPersonalizado
                              label={`${sp.nombre}${sp.obligatorio ? ' *' : ''}`}
                              value={valor}
                              disabled={locked}
                              invalido={Boolean(errorCodigo)}
                              sinRespuestaLabel="—"
                              opciones={sp.opciones_seleccion.map((opcion) => ({ valor: opcion, etiqueta: opcion }))}
                              onChange={(nuevo) => actualizarRespuestaPersonalizacion(sp.id, nuevo)}
                            />
                            <ErrorDeCampo id={errorId} mensaje={errorCodigo ? checkout.personalizacionErrors[errorCodigo] : ''} />
                          </div>
                        );
                      }
                      return (
                        <label
                          key={sp.id}
                          htmlFor={`personalizacion-${sp.id}`}
                          className="flex flex-col gap-2 text-sm text-foreground"
                        >
                          <span className="font-medium">
                            {sp.nombre}
                            {sp.obligatorio ? ' *' : ''}
                          </span>
                          <input
                            id={`personalizacion-${sp.id}`}
                            type={sp.tipo_interaccion === 'input_numero' ? 'number' : 'text'}
                            step={sp.tipo_interaccion === 'input_numero' ? 'any' : undefined}
                            value={valor}
                            disabled={locked}
                            aria-invalid={Boolean(errorCodigo)}
                            aria-describedby={errorCodigo ? errorId : undefined}
                            onChange={(e) => actualizarRespuestaPersonalizacion(sp.id, e.target.value)}
                            className={`border bg-surface px-4 py-3 outline-none ${
                              errorCodigo ? CLASES_CAMPO_CON_ERROR : 'border-border focus:border-accent'
                            }`}
                          />
                          <ErrorDeCampo id={errorId} mensaje={errorCodigo ? checkout.personalizacionErrors[errorCodigo] : ''} />
                        </label>
                      );
  };

  const { obligatorias, opcionales } = separarPersonalizaciones(catalogoUnificado);

  return (
    <>
      <PaginaCheckout
        lang={lang}
        dict={dict}
        // Con lo que el cliente ya había contestado: `page.tsx` de la portada
        // lo lee y precarga el booking bar, para no hacerlo empezar de cero
        // solo por haber vuelto a revisar algo.
        volverHref={`/${lang}?${new URLSearchParams({ day, time, people: String(people) }).toString()}`}
        volverLabel={checkout.back}
        encabezado={
          <EncabezadoCompra
            kicker={checkout.purchaseKicker}
            nombre={servicioNombre || servicio?.nombre || ''}
          />
        }
        aviso={sinLugar ? (
        <div className="mx-auto mb-2 flex max-w-6xl items-start gap-3 px-6 sm:px-8 lg:px-12">
          <div className="flex w-full flex-col gap-2 border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-foreground sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Warning size={18} className="mt-0.5 shrink-0 text-accent" />
              <p>{sinLugar.mensaje}</p>
            </div>
            {/* La alternativa se OFRECE, no se aplica. Es el cliente quien decide
                cambiar de fecha: para un turista con vuelo el jueves, el
                siguiente dia libre puede no servirle de nada. */}
            {sinLugar.alternativa && (
              <button
                type="button"
                onClick={() => {
                  const nueva = sinLugar.alternativa!;
                  setDay(nueva);
                  avisar(
                    'info',
                    dict.feedback.dateChanged.replace(
                      '{date}',
                      formatDay(fromLocalISODate(nueva), lang),
                    ),
                  );
                }}
                className="shrink-0 self-start rounded-full bg-accent px-4 py-2 text-xs font-medium text-accent-foreground transition-transform active:scale-[0.98] sm:self-auto"
              >
                {checkout.takeOffered.replace(
                  '{date}',
                  formatDay(fromLocalISODate(sinLugar.alternativa), lang),
                )}
              </button>
            )}
          </div>
        </div>
        ) : undefined}
        stepper={{ actual: pasoActualStepper, totalMovil }}
        pasos={
          <>
            <ItemPaso unida={unidaConAnterior(secuencia, 0)}>
              <CheckoutSectionCard
                title={checkout.tripHeadline}
                estado={estadoViaje}
                resumen={resumenPaso1}
                actionLabel={etiquetaAccion(crudoViaje)}
                onAction={crudoViaje === 'activo' ? undefined : () => reabrir('viaje')}
                pie={crudoViaje === 'activo' && !locked
                  ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso>
                  : undefined}
              >
                <ContenidoViaje
                  fecha={
                    <>
                      <CheckoutCalendar
                        lang={lang}
                        selected={day}
                        onSelect={setDay}
                        minDate={minDate}
                        personas={people}
                        fullLabel={checkout.dayFull}
                        weekdaysShort={checkout.weekdaysShort}
                      />
                      <p className="mt-5 border-t border-border pt-5 text-sm text-foreground">
                        {formatDay(dayDate, lang)}
                      </p>
                    </>
                  }
                  hora={pideHora ? (locked ? (
                    <p className="px-6 py-4 text-sm text-muted">
                      {checkout.hourLabel}: <span className="text-foreground">{horaTexto}</span>
                    </p>
                  ) : (
                    <TimeField
                      label={checkout.hourLabel}
                      help={booking.timeHelp}
                      value={time}
                      onChange={setTime}
                      availableHours={horasDisponibles}
                    />
                  )) : undefined}
                  personas={
                    <PeopleStepper
                      label={checkout.peopleLabel}
                      maxNotice={booking.maxPeopleNotice}
                      value={people}
                      onChange={cambiarPersonas}
                      disabled={locked}
                      onMaxAttempt={() => ayuda.tropezar('tope-personas')}
                    />
                  }
                  salida={tieneHospedaje ? (locked ? (
                    <p className="text-sm text-foreground">
                      {checkout.checkoutDateLabel}: {formatDay(fromLocalISODate(fechaSalida), lang)}
                    </p>
                  ) : (
                    <div className="border border-border bg-surface">
                      <DateField
                        lang={lang}
                        label={checkout.checkoutDateLabel}
                        value={fechaSalida}
                        onChange={setFechaSalidaManual}
                        minDate={defaultFechaSalida}
                        prevMonthLabel={booking.prevMonth}
                        nextMonthLabel={booking.nextMonth}
                        personas={people}
                        fullLabel={checkout.dayFull}
                        sinCupo
                      />
                    </div>
                  )) : undefined}
                  nota={precioPersonaExtra > 0 ? (
                    <p>
                      {checkout.extraPeopleHint
                        .replace('{included}', String(personasIncluidas))
                        .replace('{price}', currency.format(precioPersonaExtra))}
                    </p>
                  ) : undefined}
                />
              </CheckoutSectionCard>
            </ItemPaso>

            {estadoContacto && (
              <ItemPaso unida={unidaConAnterior(secuencia, 1)}>
                <CheckoutSectionCard
                  title={checkout.contactHeadline}
                  estado={estadoContacto}
                  resumen={resumenPaso2}
                  actionLabel={etiquetaAccion(crudoContacto)}
                  onAction={crudoContacto === 'activo' ? undefined : () => reabrir('contacto')}
                  pie={crudoContacto === 'activo' && !locked
                    ? <BotonPaso onClick={confirmarContacto}>{checkout.confirmStep}</BotonPaso>
                    : undefined}
                >
                  <CamposContacto
                    idPrefijo="checkout"
                    valores={contact}
                    errores={erroresCampo}
                    etiquetas={{ phone: checkout.phone, fullName: checkout.fullName, email: checkout.email }}
                    refs={{ phone: refPhone, fullName: refFullName, email: refEmail }}
                    disabled={locked}
                    onCambio={(campo, valor) => {
                      setContact((prev) => ({ ...prev, [campo]: valor }));
                      // El error se limpia al escribir: dejarlo puesto mientras el
                      // cliente corrige lo convierte en un regaño que no se calla.
                      if (erroresCampo[campo]) setErroresCampo((prev) => ({ ...prev, [campo]: undefined }));
                    }}
                  />
                </CheckoutSectionCard>
              </ItemPaso>
            )}

            {/* El punto de encuentro real y el aviso del agente ya no van aquí:
                son información de después de pagar, viven en BookingConfirmation.
                Bebidas se quitó del checkout: depende del tipo de bebida, un dato
                que el sitio no captura; la vendedora la sigue cotizando a mano en
                reservas por WhatsApp o teléfono. */}
            {estadoDetalles && (
              <ItemPaso unida={unidaConAnterior(secuencia, secuencia.length - 1)}>
                <CheckoutSectionCard
                  title={checkout.extrasStepHeadline}
                  estado={estadoDetalles}
                  resumen={
                    catalogoUnificado
                      .filter((p) => personalizacionesMap.has(p.id))
                      .map((p) => p.nombre)
                      .join(', ') ||
                    checkout.noExtrasSelected
                  }
                  actionLabel={locked ? undefined : etiquetaAccion(crudoDetalles)}
                  onAction={locked || crudoDetalles === 'activo' ? undefined : () => reabrir('detalles')}
                  pie={crudoDetalles === 'activo' && !locked
                    ? <BotonPaso conFlecha onClick={continuarAPago}>{checkout.continueToPayment || checkout.confirmStep}</BotonPaso>
                    : undefined}
                >
                  {catalogoUnificado.length === 0 && (
                    <p className="text-sm text-muted">{checkout.noExtrasSelected}</p>
                  )}
                  {obligatorias.length > 0 && (
                    <BloqueDePaso titulo={checkout.extrasRequiredLabel}>
                      {obligatorias.map(renderPersonalizacion)}
                    </BloqueDePaso>
                  )}
                  {opcionales.length > 0 && (
                    <BloqueDePaso titulo={checkout.extrasOptionalLabel} opcional={checkout.optionalTag}>
                      {opcionales.map(renderPersonalizacion)}
                    </BloqueDePaso>
                  )}
                </CheckoutSectionCard>
              </ItemPaso>
            )}

            {/* El pago es el cuarto paso: la tarjeta aparece justo debajo de las
                respuestas ya dadas, no al final del panel de resumen. */}
            {phase === 'payment' && pago && (
              <FormularioPago
                checkout={checkout}
                feedback={dict.feedback}
                ayudaMensaje={ayudaMensaje}
                pago={pago}
                onPagoConfirmado={(procesando) => {
                  setPagoProcesando(procesando);
                  setPhase('confirmed');
                }}
              />
            )}
          </>
        }
        pedido={
          // Un solo StripePanel en todo el arbol — montarlo dos veces inicializaria
          // Stripe.js y el widget de Turnstile por duplicado. En movil la zona de
          // pago se muestra al llegar al paso 4 (`pagoVisibleMovil`); antes queda
          // montada pero oculta, nunca se desmonta.
          <div ref={refStripePanel} className="scroll-mt-28">
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
                label: servicio?.nombre ?? servicioNombre ?? checkout.total,
                amount: currency.format(Number(pago.precio_total)),
              }] : lines}
              total={pago ? currency.format(Number(pago.precio_total)) : total === null ? '—' : currency.format(total)}
              amountDueNow={pago ? currency.format(Number(pago.monto_a_cobrar)) : amountDueNow === null ? '—' : currency.format(amountDueNow)}
              moneda={moneda}
              onMonedaChange={setMoneda}
              usdDisponible={usdDisponible}
              formaPago={formaPagoEfectiva}
              onFormaPagoChange={setFormaPago}
              formaPagoDisponible={permiteAnticipo}
              codigoPromocional={codigoPromocional}
              onCodigoPromocionalChange={onCodigoPromocionalChange}
              promoEstado={promoEstado}
              promoPorcentaje={promoPorcentaje}
              phase={phase}
              error={error}
              feedback={dict.feedback}
              lineasViaje={lineasViaje}
              pagoVisibleMovil={actual === 'pago' || enviando || locked}
              ayudaMensaje={ayudaMensaje}
              onSubmit={iniciarPago}
              onCaptchaToken={(token) => (captchaToken.current = token)}
            />
            {/* Fuera de la tarjeta de resumen, debajo: no es parte del desglose de
                precio, es la respuesta a "es seguro pagar aquí". En la fase de pago
                va junto al formulario de tarjeta (ver `FormularioPago`). */}
            {phase !== 'payment' && <NotaSeguridadStripe checkout={checkout} />}
          </div>
        }
      />

      <AyudaFlotante
        visible={ayuda.visible}
        etiqueta={dict.feedback.floatingHelp.label}
        cerrarLabel={dict.feedback.floatingHelp.dismiss}
        mensaje={ayuda.motivo === 'tope-personas'
          ? dict.feedback.floatingHelp.messageMaxPeople
              .replace('{name}', servicio?.nombre ?? servicioNombre ?? '')
              .replace('{max}', String(MAX_PEOPLE))
          : dict.feedback.floatingHelp.messageValidation
              .replace('{date}', formatDay(dayDate, lang))
              .replace('{people}', String(people))}
        onDescartar={ayuda.descartar}
      />

      <AnimatePresence>
        {recordatorioAbierto && (
          <AmenitiesReminder
            key="amenities-reminder"
            checkout={checkout}
            feedback={dict.feedback}
            pendientes={opcionesPendientes}
            onSeleccionarExtra={(id) => alternarPersonalizacion(id, true)}
            onContinuar={enviar}
            onCerrar={() => setRecordatorioAbierto(false)}
            enviando={enviando}
          />
        )}
      </AnimatePresence>
    </>
  );
}
