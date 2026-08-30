'use client';

import { useEffect, useMemo, useRef, useState, useLayoutEffect } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  ArrowRight,
  CaretDown,
  EnvelopeSimple,
  Lock,
  Minus,
  Phone,
  Plus,
  User,
  Warning,
} from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { AmenitiesReminder, type ExtraPendiente } from '@/components/amenities-reminder';
import { BookingConfirmation } from '@/components/booking-confirmation';
import { SiteHeader } from '@/components/site-header';
import { CheckoutCalendar } from '@/components/checkout-calendar';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CheckoutStepper } from '@/components/checkout-stepper';
import { CLASES_CAMPO_CON_ERROR, FieldError, propsDeError } from '@/components/field-error';
import { PeopleStepper } from '@/components/people-stepper';
import { StripePanel } from '@/components/stripe-panel';
import { TimeField } from '@/components/time-field';
import { useToast } from '@/components/toast';
import { WaitNotice } from '@/components/wait-notice';
import {
  ApiError,
  crearPago,
  getCupo,
  getEstadoReserva,
  getExtras,
  guardarReserva,
  validarCodigoPromocional,
  type CatalogoExtras,
  type EstadoReservaPagada,
  type ExtraCatalogo,
  type Moneda,
  type Pago,
  type Tarifa,
  type Zona,
} from '@/lib/api';
import { formatHour, fromLocalISODate } from '@/lib/dates';
import { mensajeDeAyuda, mensajeDeFallo } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import { leerRef } from '@/lib/ref';

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

  return value;
}

type CheckoutViewProps = {
  lang: Locale;
  dict: Dictionary;
  initialDay: string;
  initialTime: string;
  initialPeople: number;
  minDate: string;
  // null = el backend no dio precio (sin tarifa configurada o caido).
  tarifa: Tarifa | null;
  // `true` si day/time/people vinieron explicitos en la URL: el cliente acaba
  // de elegir viaje en el booking bar, no recargo esta pagina. Ver el efecto
  // de recuperacion mas abajo.
  queryOverride: boolean;
};

// 'recuperando': solo se pasa por aqui si esta pestana ya tenia un checkout_id
// guardado (ver useCheckoutId) — se pregunta si tiene una reserva detras antes
// de decidir si el checkout arranca vacio, precargado, o directo en la
// confirmacion.
type Phase = 'recuperando' | 'form' | 'submitting' | 'payment' | 'confirmed' | 'unavailable' | 'error';

/**
 * El texto que ve el cliente, segun lo que contesto el backend.
 *
 * Antes todo lo que no fuera 503 caia en un mensaje generico, y eso costo caro:
 * con la llave de Stripe mal capturada en Render, `crear-pago` devolvia 502 en
 * cada intento y el checkout solo decia "Algo salio mal" — sin nada que
 * separara una caida del procesador de un cobro que ya venia en curso, que son
 * dos situaciones con remedios opuestos para quien esta del otro lado.
 *
 * Lo que no se muestra es el detalle tecnico: al cliente le importa si se le
 * cobro y que hacer ahora. El diagnostico va al log del backend y a Sentry.
 */
type CampoContacto = 'fullName' | 'phone' | 'email';

/**
 * Orden en que se busca el primer campo malo para mandarle el foco. Es el orden
 * visual del formulario, no el de validacion: mandar el foco a un campo que esta
 * mas arriba de otro que tambien fallo desorienta.
 */
const ORDEN_CAMPOS: CampoContacto[] = ['phone', 'fullName', 'email'];

function mensajeDeError(
  err: unknown,
  checkout: Dictionary['checkout'],
  feedback: Dictionary['feedback'],
) {
  if (err instanceof ApiError) {
    // 502: el backend no pudo hablar con Stripe, asi que no hay ningun cobro.
    if (err.status === 502) return checkout.errorPaymentProvider;
    // 409: ya hay un intent cobrando esta reserva (apps/payments/views.py).
    // Reintentar aqui es justo lo que puede acabar en un cargo duplicado.
    if (err.status === 409) return checkout.errorPaymentInProgress;
  }
  // El resto lo resuelve el catalogo compartido, que ademas cubre el caso que
  // antes no tenia mensaje ninguno: que no haya red. Ver src/lib/errores.ts.
  return mensajeDeFallo(err, feedback.error);
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

export function CheckoutView({
  lang,
  dict,
  initialDay,
  initialTime,
  initialPeople,
  minDate,
  tarifa,
  queryOverride,
}: CheckoutViewProps) {
  const { checkout, booking, nav } = dict;
  // null mientras sessionStorage todavia no se ha leido (solo dura hasta el
  // primer useLayoutEffect del cliente — ver useCheckoutId).
  const checkoutIdValue = useCheckoutId();
  const checkoutId = checkoutIdValue?.id ?? '';
  const recuperable = checkoutIdValue?.recuperable ?? false;

  const [day, setDay] = useState(initialDay);
  const [time, setTime] = useState(initialTime);
  const [people, setPeople] = useState(initialPeople);
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
  // Sin precio en USD configurado no hay selector que ofrecer (ver
  // `usdDisponible` en StripePanel, que lo oculta entero): forzar USD aqui
  // dejaria al cliente sin forma de volver a MXN, con un total en $0.
  const [moneda, setMoneda] = useState<Moneda>(
    lang === 'en' && tarifa?.precio_usd != null ? 'USD' : 'MXN',
  );
  // Catalogo de extras (brunch, licencia, carnada, transporte, puntos de
  // encuentro) con el monto ya resuelto para `people`/`moneda` — ver el efecto
  // de abajo. null hasta la primera respuesta del backend.
  const [catalogo, setCatalogo] = useState<CatalogoExtras | null>(null);
  /**
   * `null` = el cliente no ha tocado el paso de Extras todavia, asi que vale
   * lo que el catalogo recomienda. Cualquier arreglo (incluido el vacio) es
   * una decision suya y gana sobre la recomendacion.
   *
   * Se guarda "no ha elegido" en vez de copiar los recomendados a estado
   * apenas llega el catalogo: copiarlos obliga a un efecto que sincroniza un
   * estado con otro, y ese efecto es justo el que se equivocaba de condicion
   * y dejaba el paso vacio. Aqui la seleccion efectiva se deriva y no puede
   * desalinearse.
   */
  const [extrasElegidos, setExtrasElegidos] = useState<number[] | null>(null);
  const [transporteModo, setTransporteModo] = useState<'ninguno' | 'punto' | 'direccion'>('ninguno');
  const [puntoEncuentroId, setPuntoEncuentroId] = useState<number | null>(null);
  const [direccionPersonalizada, setDireccionPersonalizada] = useState('');
  // Cuantas personas eligio el cliente para un extra con `cantidad_editable`
  // (ver ExtraCatalogo) — solo importa para esos, id de ExtrasItem -> cantidad.
  // Ausente = todo el grupo, mismo comportamiento que un extra sin este control.
  const [cantidadesExtras, setCantidadesExtras] = useState<Record<number, number>>({});
  // Cuantas personas usan el transporte. `null` = todo el grupo (de siempre).
  const [personasTransporte, setPersonasTransporte] = useState<number | null>(null);
  /**
   * En que quedo el efecto de recuperacion, para que los extras
   * preseleccionados del catalogo (licencia, carnada) no compitan con una
   * seleccion repuesta de una reserva a medio pagar.
   *
   * Antes esto era solo `recuperable`, y ahi estaba el bug: `recuperable` dice
   * que esta pestana TRAE un checkout_id guardado, no que exista una reserva
   * detras. Cualquier pestana ya usada (todas, despues del primer checkout)
   * entraba con `recuperable` en true, y si el backend contestaba 404 —el caso
   * normal: la reserva vieja ya se pago o nunca existio— nadie aplicaba los
   * defaults y el paso de Extras arrancaba vacio para siempre.
   */
  // 'pendiente' como estado inicial es conservador: si el useLayoutEffect
  // descubre que no hay sessionStorage, lo cambia a 'sin-reserva' de inmediato.
  // Esto evita que el codigo de extras asuma defaults antes de saber si hay
  // una reserva que recuperar.
  const [recuperacion, setRecuperacion] = useState<'pendiente' | 'sin-reserva' | 'repuesta'>(
    'pendiente',
  );
  const [formaPago, setFormaPago] = useState<'completo' | 'anticipo'>('completo');
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
  // La fase inicial se decide en el useLayoutEffect de abajo, una vez que
  // checkoutIdValue esta disponible. Antes de eso se usa 'recuperando' como
  // pantalla de espera neutral — muestra el spinner de "buscando tu reserva"
  // sin comprometer nada hasta saber si hay sessionStorage que recuperar.
  const [phase, setPhase] = useState<Phase>('recuperando');
  const phaseInicializada = useRef(false);
  useLayoutEffect(() => {
    // Solo se ejecuta una vez, cuando checkoutIdValue pasa de null a un valor
    // real. A partir de ahi la logica de recuperacion toma el control.
    if (checkoutIdValue === null || phaseInicializada.current) return;
    phaseInicializada.current = true;
    setPhase(recuperable ? 'recuperando' : tarifa ? 'form' : 'unavailable');
    setRecuperacion(recuperable ? 'pendiente' : 'sin-reserva');
  }, [checkoutIdValue, recuperable, tarifa]);
  const [error, setError] = useState('');
  // Monto real cobrado, cuando la confirmacion viene de una reserva recuperada
  // (ver el efecto de abajo) en vez de un pago recien hecho en esta misma
  // visita. `null` = mostrar lo que ya calcula el resto del checkout
  // (`amountDueNow`/`total`), que es lo correcto para un pago fresco: la
  // reserva recuperada puede llevar otra tarifa o amenidades que ya no estan
  // en el estado local, asi que aqui se confia lo que de verdad se cobro y no
  // lo que la tarifa de hoy recalcularia.
  const [recuperadoPagado, setRecuperadoPagado] = useState<number | null>(null);
  const [recuperadoSaldo, setRecuperadoSaldo] = useState<number | null>(null);
  // Desglose de extras/transporte ya congelado al pagar, para una reserva
  // recuperada. Se guarda crudo (no formateado) porque `currency` depende de
  // `moneda`, y `moneda` recien se esta fijando en el mismo efecto que llena
  // esto — el formateo real ocurre despues, al construir `lineasExtrasRecuperadas`.
  const [recuperadoExtras, setRecuperadoExtras] = useState<EstadoReservaPagada['extras']>([]);
  const [recuperadoTransporteMonto, setRecuperadoTransporteMonto] = useState<number | null>(null);
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
        cupo = await getCupo(day, people);
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
        cupo.motivo_no_disponible === 'sin_panga'
          ? checkout.noBoatForGroupNotice
          : checkout.dayFullOffer;

      setSinLugar({
        mensaje: plantilla
          .replace('{date}', formatDay(fromLocalISODate(day), lang))
          .replace('{people}', String(people)),
        alternativa: cupo.proxima_disponible,
      });
    })();
  }, [day, people, lang, checkout.dayFullOffer, checkout.noBoatForGroupNotice]);

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
        resultado = await validarCodigoPromocional(codigo, contact.email);
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
  }, [codigoPromocional, contact.email]);

  /**
   * Catalogo de extras con el monto ya resuelto por el servidor para
   * `people`/`moneda` — la web nunca reimplementa si un extra cobra por
   * persona ni el umbral del recargo de transporte (ver apps/fleet/views.py).
   * Se vuelve a pedir con cada cambio de grupo o moneda, porque los montos
   * dependen de los dos.
   */
  useEffect(() => {
    let cancelado = false;

    (async () => {
      let datos: CatalogoExtras;
      try {
        datos = await getExtras(people, moneda);
      } catch {
        // Igual que getCupo: es ayuda adelantada, nunca debe trabar el checkout.
        return;
      }
      if (!cancelado) setCatalogo(datos);
    })();

    return () => {
      cancelado = true;
    };
  }, [people, moneda]);

  /**
   * Que extras van marcados ahora mismo.
   *
   * Mientras el cliente no toque el paso, valen los que el catalogo marca como
   * recomendados (licencia y carnada). Deriva en vez de sincronizar, asi que
   * da igual el orden en que lleguen el catalogo y el veredicto de la
   * recuperacion — antes eso era un efecto condicionado a `recuperable`, que
   * es "esta pestana trae un checkout_id guardado" y no "hay una reserva
   * detras": cualquier pestana ya usada dejaba el paso vacio.
   */
  const extrasSeleccionados =
    extrasElegidos ??
    (recuperacion === 'sin-reserva' && catalogo
      ? catalogo.extras.filter((e) => e.preseleccionado).map((e) => e.id)
      : []);

  const alternarExtra = (id: number, marcado: boolean) => {
    setExtrasElegidos(
      marcado ? [...extrasSeleccionados, id] : extrasSeleccionados.filter((x) => x !== id),
    );
    // Sin cantidad elegida no pasa nada (se deriva "todo el grupo" por
    // default), pero al desmarcar se limpia para no arrastrar un numero de
    // una eleccion anterior si el cliente lo vuelve a marcar despues.
    if (!marcado) {
      setCantidadesExtras((actual) => {
        if (!(id in actual)) return actual;
        const resto = { ...actual };
        delete resto[id];
        return resto;
      });
    }
  };

  // Solo se ofrecen dolares si el negocio fijo un precio en dolares.
  const usdDisponible = tarifa?.precio_usd != null;
  const tourPrice = tarifa ? Number(moneda === 'MXN' ? tarifa.precio : tarifa.precio_usd) : null;

  const currency = useMemo(
    () => new Intl.NumberFormat(intlLocale(lang), { style: 'currency', currency: moneda }),
    [lang, moneda],
  );

  const extrasCatalogo = catalogo?.extras ?? [];
  const transporteCatalogo = catalogo?.transporte ?? [];
  const puntosEncuentro = catalogo?.puntos_encuentro ?? [];

  const getNombreExtra = (e: { tipo?: string; nombre: string }) =>
    (e.tipo && (checkout.extrasNames as Record<string, string>)?.[e.tipo]) || e.nombre;

  const getDescripcionExtra = (e: { tipo?: string; descripcion?: string }) =>
    (e.tipo && (checkout.extrasDescriptions as Record<string, string>)?.[e.tipo]) || e.descripcion;

  const extrasSeleccionadosItems = extrasCatalogo.filter((e) => extrasSeleccionados.includes(e.id));

  // "2 de 5": misma leyenda para el extra con cantidad editable y para el
  // transporte, para que las dos digan la cantidad elegida de la misma forma.
  const deLabel = (cantidad: number, total: number) =>
    checkout.cantidadDeLabel.replace('{cantidad}', String(cantidad)).replace('{total}', String(total));

  // Cuantas personas lleva ESTE extra. Solo se aparta de `people` (todo el
  // grupo, el comportamiento de siempre) si el item es `cantidad_editable`
  // (ej. licencia: alguien puede ya traer la suya tramitada aparte) y el
  // cliente eligio menos — acotado por si `people` bajo despues de elegirla.
  const cantidadDeExtra = (item: ExtraCatalogo) =>
    item.cantidad_editable ? Math.min(cantidadesExtras[item.id] ?? people, people) : people;

  const ajustarCantidadExtra = (item: ExtraCatalogo, delta: number) =>
    setCantidadesExtras((actual) => {
      const actualCantidad = Math.min(actual[item.id] ?? people, people);
      return { ...actual, [item.id]: Math.min(people, Math.max(1, actualCantidad + delta)) };
    });

  // `monto` viene TOTAL para el grupo completo (ver apps/fleet/serializers.py,
  // ExtrasItemSerializer.get_monto). Para uno `cantidad_editable` se
  // reescala al precio unitario (monto/people) por la cantidad elegida, que
  // puede ser menor al grupo — para los demas se suma tal cual, como siempre.
  const cargoExtras = extrasSeleccionadosItems.reduce((acc, e) => {
    if (e.monto == null) return acc;
    const monto = Number(e.monto);
    if (!e.cantidad_editable) return acc + monto;
    return acc + (monto / people) * cantidadDeExtra(e);
  }, 0);

  // La zona del traslado: la del hotel elegido, o siempre 'periferia' si el cliente escribio
  // a mano con "otra direccion" (para cubrir toda la zona de La Paz con tarifa fija clara).
  const zonaTransporteActual: Zona | null =
    transporteModo === 'punto'
      ? (puntosEncuentro.find((p) => p.id === puntoEncuentroId)?.zona ?? null)
      : transporteModo === 'direccion'
        ? 'periferia'
        : null;
  const transportePrecio = zonaTransporteActual
    ? (transporteCatalogo.find((t) => t.zona === zonaTransporteActual) ?? null)
    : null;
  const cargoTransporte = transportePrecio?.monto != null ? Number(transportePrecio.monto) : 0;
  // Acotado al grupo actual, igual que `cantidadDeExtra`. El precio mostrado
  // arriba sigue siendo el del catalogo para el grupo completo a proposito
  // (el recargo de transporte no escala linealmente, ver
  // apps/payments/pricing.py) — esto solo es lo que se manda al elegir.
  const personasTransporteEfectivo = Math.min(personasTransporte ?? people, people);

  const ajustarPersonasTransporte = (delta: number) =>
    setPersonasTransporte((actual) => {
      const actualCantidad = Math.min(actual ?? people, people);
      return Math.min(people, Math.max(1, actualCantidad + delta));
    });

  /**
   * Las tres formas de resolver el traslado, cada una con el control que le
   * toca. Se arma como lista y no como tres bloques sueltos de JSX porque el
   * control de cada opcion se pinta DENTRO de su propia tarjeta: la unica
   * forma de garantizar que el select no se vuelva a separar de la opcion que
   * lo revela es que ni siquiera exista un lugar fuera donde ponerlo.
   *
   * Ninguno lleva `disabled`: el `<fieldset disabled>` que los envuelve ya
   * apaga todo lo que tiene adentro.
   */
  const opcionesTransporte: {
    valor: 'ninguno' | 'punto' | 'direccion';
    etiqueta: string;
    panel?: React.ReactNode;
  }[] = [
    { valor: 'ninguno', etiqueta: checkout.transporte.none },
    ...(puntosEncuentro.length > 0
      ? [
          {
            valor: 'punto' as const,
            etiqueta: checkout.transporte.hotelOption,
            panel: (
              <label className="flex flex-col gap-1.5 text-sm">
                <span className="text-muted">{checkout.transporte.selectHotelPlaceholder}</span>
                <span className="relative">
                  <select
                    value={puntoEncuentroId ?? ''}
                    onChange={(e) =>
                      setPuntoEncuentroId(e.target.value ? Number(e.target.value) : null)
                    }
                    // `appearance-none` + caret propio: con la flecha nativa,
                    // el control se ve de otro sistema operativo en cada
                    // maquina y rompe con el resto del checkout.
                    className="w-full appearance-none border border-border bg-background py-3 pr-11 pl-4 text-sm text-foreground outline-none transition-colors focus:border-accent disabled:opacity-60"
                  >
                    <option value="" disabled>
                      {checkout.transporte.selectHotelPlaceholder}
                    </option>
                    {puntosEncuentro.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.nombre}
                      </option>
                    ))}
                  </select>
                  <CaretDown
                    size={14}
                    weight="bold"
                    className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-muted"
                  />
                </span>
              </label>
            ),
          },
        ]
      : []),
    {
      valor: 'direccion',
      etiqueta: checkout.transporte.customOption,
      panel: (
        <div className="flex flex-col gap-2.5">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">{checkout.transporte.addressPlaceholder}</span>
            <input
              type="text"
              value={direccionPersonalizada}
              onChange={(e) => setDireccionPersonalizada(e.target.value)}
              placeholder={checkout.transporte.addressPlaceholder}
              className="w-full border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-accent disabled:opacity-60"
            />
          </label>
          <p className="text-xs leading-relaxed text-muted">
            {checkout.transporte.customAddressNote}
          </p>
        </div>
      ),
    },
  ];

  /**
   * Todo lo del catalogo que el cliente NO lleva: es lo que el recordatorio
   * de antes de pagar puede ofrecerle.
   *
   * Cuenta cualquier extra sin marcar, no solo los recomendados. Filtrarlo a
   * `preseleccionado` dejaba el recordatorio muerto desde que los
   * recomendados empezaron a venir marcados —la lista salia siempre vacia— y
   * de paso nunca ofrecia el brunch, que es el unico que no viene marcado y
   * por lo tanto el unico que de verdad hacia falta ofrecer.
   *
   * Sin precio en la moneda elegida no se ofrece: no se puede cobrar.
   */
  const extrasPendientes: ExtraPendiente[] = extrasCatalogo
    .filter((e) => !extrasSeleccionados.includes(e.id) && e.monto !== null)
    .map((e) => ({ id: e.id, nombre: getNombreExtra(e), monto: currency.format(Number(e.monto)) }));

  /**
   * El traslado tambien cuenta como algo que le falta al cliente, pero no
   * cabe en `extrasPendientes`: elegirlo exige decir desde donde lo recogen,
   * y eso no se contesta con una casilla dentro de un modal. Se ofrece con el
   * precio de la zona mas barata ("Desde X") y un boton que devuelve al paso.
   */
  const montosTransporte = transporteCatalogo
    .map((t) => (t.monto === null ? null : Number(t.monto)))
    .filter((m): m is number => m !== null);
  const transportePendiente =
    transporteModo === 'ninguno' && montosTransporte.length > 0
      ? {
          etiqueta: checkout.transporte.headline,
          monto: checkout.transporte.fromPrice.replace(
            '{price}',
            currency.format(Math.min(...montosTransporte)),
          ),
          onElegir: () => {
            setRecordatorioAbierto(false);
            setExtrasConfirmado(false);
            setPasoEditando(3);
          },
        }
      : null;

  // El precio es por viaje (la reserva es de la embarcacion completa), pero
  // pasando de las personas incluidas se suma un cargo por cada una. El servidor
  // recalcula esto mismo al crear el pago: aqui solo se muestra.
  const personasIncluidas = tarifa?.personas_incluidas ?? 0;
  const precioPersonaExtra = tarifa
    ? Number(moneda === 'MXN' ? tarifa.precio_persona_extra : tarifa.precio_persona_extra_usd)
    : 0;
  const personasExtra = Math.max(0, people - personasIncluidas);
  const cargoPersonas = personasExtra * (precioPersonaExtra || 0);

  const subtotalSinDescuento =
    tourPrice === null ? null : tourPrice + cargoPersonas + cargoExtras + cargoTransporte;

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
    ...extrasSeleccionadosItems
      .filter((e) => e.monto != null)
      .map((e) => {
        const totalExtra = Number(e.monto);
        const nombreTraducido = getNombreExtra(e);
        if (e.cantidad_editable) {
          const cantidad = cantidadDeExtra(e);
          return {
            label: `${nombreTraducido} (${deLabel(cantidad, people)})`,
            amount: currency.format((totalExtra / people) * cantidad),
          };
        }
        return {
          label: e.cobrar_por_persona
            ? `${nombreTraducido} (${people} × ${currency.format(totalExtra / people)})`
            : nombreTraducido,
          amount: currency.format(totalExtra),
        };
      }),
    ...(transportePrecio?.monto != null
      ? [
          {
            label: checkout.transporte.headline,
            amount: currency.format(Number(transportePrecio.monto)),
          },
        ]
      : []),
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
    ...recuperadoExtras
      .filter((e) => e.monto != null)
      .map((e) => {
        const totalExtra = Number(e.monto);
        // `cantidad` ya es la congelada real: si vino menor al grupo, este
        // extra tenia `cantidad_editable` y el cliente pidio menos.
        if (e.cantidad !== null && e.cantidad !== people) {
          return {
            label: `${e.nombre} (${deLabel(e.cantidad, people)})`,
            amount: currency.format(totalExtra),
          };
        }
        return {
          label: e.cobrar_por_persona
            ? `${e.nombre} (${people} × ${currency.format(totalExtra / people)})`
            : e.nombre,
          amount: currency.format(totalExtra),
        };
      }),
    ...(recuperadoTransporteMonto !== null
      ? [{ label: checkout.transporte.headline, amount: currency.format(recuperadoTransporteMonto) }]
      : []),
    ...(recuperadoDescuento !== null
      ? [
          {
            label: `${checkout.promoCode.discountLabel} (${recuperadoCodigoPromocional})`,
            amount: `-${currency.format(recuperadoDescuento)}`,
          },
        ]
      : []),
  ];

  const lines =
    tourPrice === null
      ? []
      : [
          { label: checkout.tourLabel, amount: currency.format(tourPrice) },
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
    total === null ? null : formaPago === 'completo' ? total : Math.round(total * 0.3 * 100) / 100;

  const dayDate = useMemo(() => fromLocalISODate(day), [day]);

  /** Que campo esta mal y por que. Vacio = ninguno. */
  const [erroresCampo, setErroresCampo] = useState<Partial<Record<CampoContacto, string>>>({});

  // Cuantos de los tres pasos ya se ven. Empieza en 1: dia/hora/personas llegan
  // precargados desde la barra de reserva, asi que el primer paso no tiene un
  // momento natural de "ya se lleno" — necesita un click explicito para avanzar.
  const [pasosVisibles, setPasosVisibles] = useState(1);
  // El paso 3 (extras) no tiene un dato que validar como el 1 o el 2 — es una
  // sola casilla opcional — asi que necesita su propio "ya termine aqui" en
  // vez de derivarlo de `pasosVisibles`. Confirmarlo es lo que revela el
  // panel de pago completo en movil y adelanta el stepper al paso 4.
  const [extrasConfirmado, setExtrasConfirmado] = useState(false);
  // Que paso ya confirmado se reabrio a mano con "Cambiar". `null` = ninguno,
  // todo se muestra segun `pasosVisibles` como siempre. Reabrir no reinicia
  // nada: el dato ya validado se queda en su estado normal, esto solo decide
  // que tarjeta se ve expandida.
  const [pasoEditando, setPasoEditando] = useState<number | null>(null);
  const sinMovimiento = useReducedMotion();

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
        estado = await getEstadoReserva(checkoutId);
      } catch {
        // 404 (nada que recuperar), sin red, lo que sea: seguir como si esta
        // pestana no tuviera nada guardado. Nunca debe trabar el checkout.
        if (!cancelado) {
          setRecuperacion('sin-reserva');
          setPhase(tarifa ? 'form' : 'unavailable');
        }
        return;
      }
      if (cancelado) return;

      if (estado.estado === 'pagada') {
        setReservaId(estado.reserva_id);
        setDay(estado.fecha);
        setTime(estado.hora);
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
        setRecuperadoExtras(estado.extras);
        setRecuperadoTransporteMonto(
          estado.transporte?.monto != null ? Number(estado.transporte.monto) : null,
        );
        setRecuperadoCodigoPromocional(estado.codigo_promocional);
        setRecuperadoDescuento(
          estado.descuento_aplicado !== null ? Number(estado.descuento_aplicado) : null,
        );
        // Esta pantalla no tiene paso de Extras que precargar, pero el efecto
        // de los defaults no puede quedarse esperando un veredicto que nunca
        // llega: si el cliente vuelve a reservar en esta misma pestana, el
        // paso arrancaria vacio otra vez.
        setRecuperacion('sin-reserva');
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
          setTime(estado.hora);
          setPeople(estado.numero_personas);
        }
        setContact({
          fullName: estado.nombre_cliente,
          phone: estado.telefono_cliente,
          email: estado.correo_cliente,
        });
        setMoneda(estado.moneda);
        setExtrasElegidos(estado.extras.map((e) => e.id));
        // Cantidad ya elegida para un extra con `cantidad_editable` (ver
        // ExtraCatalogo) — sin esto, recargar la pagina la borraria en silencio.
        setCantidadesExtras(
          Object.fromEntries(
            estado.extras.filter((e) => e.cantidad != null).map((e) => [e.id, e.cantidad as number]),
          ),
        );
        // Lo que el cliente ya habia elegido gana sobre los recomendados del
        // catalogo (ver el efecto de los defaults, mas arriba).
        setRecuperacion('repuesta');
        if (estado.transporte?.punto_encuentro) {
          setTransporteModo('punto');
          setPuntoEncuentroId(estado.transporte.punto_encuentro);
          setPersonasTransporte(estado.transporte.cantidad);
        } else if (estado.transporte) {
          setTransporteModo('direccion');
          setDireccionPersonalizada(estado.transporte.direccion_personalizada);
          setPersonasTransporte(estado.transporte.cantidad);
        } else {
          setTransporteModo('ninguno');
        }
        if (estado.forma_pago) setFormaPago(estado.forma_pago);
        setPasosVisibles(3);
        setExtrasConfirmado(true);
        setPhase(tarifa ? 'form' : 'unavailable');
        return;
      }

      // 'cancelada': nada que reponer — esta reserva ya no sirve. Se sigue con
      // el formulario vacio normal, como si no hubiera nada guardado.
      setRecuperacion('sin-reserva');
      setPhase(tarifa ? 'form' : 'unavailable');
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

  // Antes, al revelarse un paso nuevo, la pagina lo traia a la vista con
  // `scrollIntoView`: el paso 1 se quedaba expandido entero (calendario, hora,
  // personas) y el 2 quedaba fuera de cuadro, abajo del todo. Ahora el paso
  // recien confirmado se colapsa solo a un renglon (`colapsado1`/`colapsado2`
  // abajo), asi que el siguiente aparece justo debajo de donde el cliente ya
  // esta mirando — el salto de scroll dejo de hacer falta.

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
      const primero = ORDEN_CAMPOS.find((campo) => errores[campo]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }

    setPasosVisibles(3);
    if (pasoEditando === 2) setPasoEditando(null);
  };

  /** Primer paso del pago: valida, y antes de tocar la red ofrece las amenidades. */
  const iniciarPago = () => {
    const errores = validarContacto();
    setErroresCampo(errores);

    if (Object.keys(errores).length > 0) {
      // El foco salta al primer campo malo. Sin esto, quien navega con teclado o
      // con lector de pantalla no tiene forma de enterarse de que hay un error:
      // el mensaje existe visualmente y para el nadie lo dijo.
      const primero = ORDEN_CAMPOS.find((campo) => errores[campo]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }

    // Sin deslinde aceptado no hay reserva; el backend lo rechaza igual. Este
    // si va al bloque de error: la casilla vive junto al boton de pagar, asi que
    // el mensaje ya esta al lado de su causa.
    if (!waiverAccepted) {
      setError(checkout.waiver.missing);
      setPhase('error');
      return;
    }

    if (extrasPendientes.length > 0 || transportePendiente) {
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
        hora: time,
        numero_personas: people,
        nombre_cliente: contact.fullName,
        telefono_cliente: contact.phone,
        correo_cliente: contact.email,
        moneda,
        deslinde_aceptado: waiverAccepted,
        // El nombre del deslinde es el que el cliente ya escribio en sus datos:
        // pedirlo dos veces no aporta nada y estorba el checkout.
        deslinde_nombre: contact.fullName.trim(),
        // La seleccion viaja con la reserva, sin precio: crear-pago la congela
        // con el catalogo vigente al pagar (ver backend/apps/bookings/serializers.py).
        // `cantidad` solo se manda si el item la deja elegir (ver ExtraCatalogo).
        extras: extrasSeleccionados.map((id) => {
          const item = extrasCatalogo.find((e) => e.id === id);
          return { id, cantidad: item?.cantidad_editable ? cantidadDeExtra(item) : undefined };
        }),
        transporte:
          transporteModo === 'ninguno'
            ? null
            : transporteModo === 'punto'
              ? { punto_encuentro: puntoEncuentroId, cantidad: personasTransporteEfectivo }
              : {
                  direccion_personalizada: direccionPersonalizada.trim(),
                  zona: 'periferia',
                  cantidad: personasTransporteEfectivo,
                },
        // A quien le cuenta la venta, si el cliente llego por el link de alguien.
        ref: leerRef(),
        captcha_token: captchaToken.current,
      });

      setReservaId(reserva.id);

      const pagoResponse = await crearPago(reserva.id, {
        checkout_id: checkoutId,
        forma_pago: formaPago,
        // Solo si la validacion en vivo lo dio por bueno; `crear-pago` lo
        // vuelve a validar de todos modos con el subtotal real (ver
        // apps/payments/views.py, `_resolver_codigo_promocional`).
        codigo_promocional:
          promoEstado === 'valido' ? codigoPromocional.trim().toUpperCase() : undefined,
      });

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

  // Colapsado = ya confirmado y no se esta reabriendo a mano. El paso 3
  // (extras) deja de poderse reabrir una vez `locked`: el checkbox ya esta
  // deshabilitado, reabrirlo no dejaria cambiar nada — por eso ese caso
  // ignora `pasoEditando` a proposito.
  const colapsado1 = pasosVisibles > 1 && pasoEditando !== 1;
  const colapsado2 = pasosVisibles > 2 && pasoEditando !== 2;
  const colapsado3 = locked || (extrasConfirmado && pasoEditando !== 3);

  const resumenPaso1 = `${formatDay(dayDate, lang)} · ${formatHour(time)} · ${people} ${checkout.peopleLabel.toLowerCase()}`;
  const resumenPaso2 = `${contact.fullName} · ${contact.phone}`;

  // El stepper de arriba cuenta el pago como paso 4 en cuanto el paso 3 se
  // confirma — ahi es cuando el panel de pago completo aparece en movil — o
  // antes si ya se mando el formulario (desde escritorio el panel siempre
  // estuvo a la vista, sin pasar por el boton de extras).
  const pasoActualStepper =
    phase === 'submitting' || phase === 'payment' || extrasConfirmado ? 4 : pasosVisibles;

  // Lo que se le manda a la vendedora si el cliente usa la salida de emergencia
  // de un error. Lleva su fecha, hora y grupo para que ella no tenga que
  // preguntarlos y el no tenga que redactar nada ya estando frustrado.
  const ayudaMensaje = mensajeDeAyuda(dict.feedback.helpMessage, {
    fecha: formatDay(dayDate, lang),
    hora: formatHour(time),
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
        hora={formatHour(time)}
        personas={people}
        // Vacio en una reserva repuesta: `EstadoReservaView` solo devuelve el
        // monto cobrado en la rama `pagada`, no el desglose, y rearmarlo con
        // el catalogo de hoy podria enseñar un precio distinto del pagado.
        extras={recuperadoPagado !== null ? lineasExtrasRecuperadas : lineasExtras}
        // Un pago recuperado manda su propio monto (lo que Stripe cobro de
        // verdad): la tarifa de hoy o las amenidades en el estado local pueden
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

  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} />

      {/* SiteHeader es `fixed` y no reserva espacio: sin `--nav-alto` (ver
          globals.css) el contenido arrancaria debajo de la barra. El 1.5rem es
          la separacion que llevaba de siempre. */}
      <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
        <Link
          // Con lo que el cliente ya habia contestado: `page.tsx` de la portada
          // lo lee y precarga el booking bar, para no hacerlo empezar de cero
          // solo por haber vuelto a revisar algo.
          href={`/${lang}?${new URLSearchParams({ day, time, people: String(people) }).toString()}`}
          className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {checkout.back}
        </Link>
      </div>

      {sinLugar && (
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
      )}

      <CheckoutStepper stepper={checkout.stepper} actual={pasoActualStepper} />

      {/* 3fr/2fr: los pasos necesitan el ancho (calendario, formulario), el
          resumen es una columna de cifras y se lee mejor angosta. */}
      <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex min-w-0 flex-col gap-6">
          <CheckoutSectionCard
            title={checkout.tripHeadline}
            estado={colapsado1 ? 'completado' : pasoEditando === 1 ? 'editando' : 'activo'}
            resumen={resumenPaso1}
            actionLabel={colapsado1 ? checkout.changeStep : pasoEditando === 1 ? checkout.doneEditing : undefined}
            onAction={() => setPasoEditando(colapsado1 ? 1 : null)}
          >
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

            {/* Hora y personas siguen siendo editables aqui: cambiar de idea no
                deberia obligar a volver a la portada. */}
            <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
              {locked ? (
                <p className="px-6 py-4 text-sm text-muted">
                  {checkout.hourLabel}: <span className="text-foreground">{formatHour(time)}</span>
                </p>
              ) : (
                <TimeField
                  label={checkout.hourLabel}
                  help={booking.timeHelp}
                  value={time}
                  onChange={setTime}
                />
              )}

              <PeopleStepper
                label={checkout.peopleLabel}
                maxNotice={booking.maxPeopleNotice}
                value={people}
                onChange={setPeople}
                disabled={locked}
              />
            </div>

            {precioPersonaExtra > 0 && (
              <p className="mt-2 px-6 text-xs text-muted">
                {checkout.extraPeopleHint
                  .replace('{included}', String(personasIncluidas))
                  .replace('{price}', currency.format(precioPersonaExtra))}
              </p>
            )}

            {/* Dia, hora y personas llegan precargados desde la barra de la
                portada: no hay un "se acaba de llenar" que dispare el paso
                siguiente solo, hace falta que el cliente lo confirme. */}
            {pasosVisibles === 1 && (
              <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-foreground">{checkout.tripConfirmQuestion}</p>
                <button
                  type="button"
                  onClick={() => setPasosVisibles(2)}
                  className="shrink-0 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]"
                >
                  {checkout.confirmStep}
                </button>
              </div>
            )}
          </CheckoutSectionCard>

          {pasosVisibles < 2 ? null : (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <CheckoutSectionCard
                title={checkout.contactHeadline}
                estado={colapsado2 ? 'completado' : pasoEditando === 2 ? 'editando' : 'activo'}
                resumen={resumenPaso2}
                actionLabel={
                  colapsado2 ? checkout.changeStep : pasoEditando === 2 ? checkout.doneEditing : undefined
                }
                onAction={() => setPasoEditando(colapsado2 ? 2 : null)}
              >
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
                        disabled={locked}
                        value={contact.phone}
                        onChange={(e) => {
                          setContact((prev) => ({ ...prev, phone: e.target.value }));
                          // El error se limpia al escribir: dejarlo puesto mientras el
                          // cliente corrige lo convierte en un regano que no se calla.
                          if (erroresCampo.phone)
                            setErroresCampo((prev) => ({ ...prev, phone: undefined }));
                        }}
                        {...propsDeError('error-phone', Boolean(erroresCampo.phone))}
                        className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                          erroresCampo.phone
                            ? CLASES_CAMPO_CON_ERROR
                            : 'border-border focus:border-accent'
                        }`}
                      />
                    </span>
                    {erroresCampo.phone && (
                      <FieldError id="error-phone" mensaje={erroresCampo.phone} />
                    )}
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
                        disabled={locked}
                        value={contact.fullName}
                        onChange={(e) => {
                          setContact((prev) => ({ ...prev, fullName: e.target.value }));
                          // El error se limpia al escribir: dejarlo puesto mientras el
                          // cliente corrige lo convierte en un regano que no se calla.
                          if (erroresCampo.fullName)
                            setErroresCampo((prev) => ({ ...prev, fullName: undefined }));
                        }}
                        {...propsDeError('error-fullName', Boolean(erroresCampo.fullName))}
                        className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                          erroresCampo.fullName
                            ? CLASES_CAMPO_CON_ERROR
                            : 'border-border focus:border-accent'
                        }`}
                      />
                    </span>
                    {erroresCampo.fullName && (
                      <FieldError id="error-fullName" mensaje={erroresCampo.fullName} />
                    )}
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
                        disabled={locked}
                        value={contact.email}
                        onChange={(e) => {
                          setContact((prev) => ({ ...prev, email: e.target.value }));
                          // El error se limpia al escribir: dejarlo puesto mientras el
                          // cliente corrige lo convierte en un regano que no se calla.
                          if (erroresCampo.email)
                            setErroresCampo((prev) => ({ ...prev, email: undefined }));
                        }}
                        {...propsDeError('error-email', Boolean(erroresCampo.email))}
                        className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                          erroresCampo.email
                            ? CLASES_CAMPO_CON_ERROR
                            : 'border-border focus:border-accent'
                        }`}
                      />
                    </span>
                    {erroresCampo.email && (
                      <FieldError id="error-email" mensaje={erroresCampo.email} />
                    )}
                  </label>
                </div>

                {(pasosVisibles === 2 || pasoEditando === 2) && (
                  <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-foreground">{checkout.contactConfirmQuestion}</p>
                    <button
                      type="button"
                      onClick={confirmarContacto}
                      className="shrink-0 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]"
                    >
                      {checkout.confirmStep}
                    </button>
                  </div>
                )}
              </CheckoutSectionCard>
            </motion.div>
          )}

          {/* El punto de encuentro real y el aviso del agente ya no van aqui:
              son informacion de despues de pagar, viven en
              BookingConfirmation. Bebidas se quito del checkout: depende del
              tipo de bebida, un dato que el sitio no captura; la vendedora la
              sigue cotizando a mano en reservas por WhatsApp o telefono. */}
          {pasosVisibles < 3 ? null : (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <CheckoutSectionCard
                title={checkout.extrasStepHeadline}
                estado={colapsado3 ? 'completado' : pasoEditando === 3 ? 'editando' : 'activo'}
                resumen={
                  [...extrasSeleccionadosItems.map((e) => getNombreExtra(e)), ...(transporteModo !== 'ninguno' ? [checkout.transporte.headline] : [])].join(', ') ||
                  checkout.noExtrasSelected
                }
                actionLabel={
                  colapsado3 && !locked
                    ? checkout.changeStep
                    : pasoEditando === 3
                      ? checkout.doneEditing
                      : undefined
                }
                onAction={locked ? undefined : () => setPasoEditando(colapsado3 ? 3 : null)}
              >
                <div className="flex flex-col gap-2">
                  {extrasCatalogo.map((item) => (
                    <div key={item.id}>
                      <label className="flex items-start justify-between gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface">
                        <span className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={extrasSeleccionados.includes(item.id)}
                            disabled={locked}
                            onChange={(e) => alternarExtra(item.id, e.target.checked)}
                            className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                          />
                          <span>
                            {getNombreExtra(item)}
                            {item.preseleccionado && (
                              <span className="ml-2 text-xs font-medium text-accent">
                                {checkout.recommendedBadge}
                              </span>
                            )}
                            {getDescripcionExtra(item) && (
                              <span className="block text-xs text-muted">{getDescripcionExtra(item)}</span>
                            )}
                            {item.preseleccionado && checkout.extrasHints[item.tipo] && (
                              <span className="block text-xs text-muted">
                                {checkout.extrasHints[item.tipo]}
                              </span>
                            )}
                          </span>
                        </span>
                        <span className="shrink-0 text-right text-muted">
                          {item.monto === null
                            ? checkout.extrasUnavailableInCurrency
                            : currency.format(Number(item.monto))}
                          {item.cobrar_por_persona && item.monto !== null && (
                            <span className="block text-xs">{checkout.extrasPerPerson}</span>
                          )}
                        </span>
                      </label>

                      {/* Solo si el item lo permite (ej. licencia: alguien puede
                          ya traer la suya tramitada aparte) y hay mas de una
                          persona entre quien repartir. Pegado a la tarjeta que
                          lo revela, no suelto al fondo del grupo. */}
                      {item.cantidad_editable &&
                        extrasSeleccionados.includes(item.id) &&
                        people > 1 && (
                          <div className="flex items-center justify-between gap-3 border border-t-0 border-border bg-surface px-4 py-2.5 text-sm text-foreground">
                            <span className="text-muted">{checkout.licenseQuantity.question}</span>
                            <span className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => ajustarCantidadExtra(item, -1)}
                                disabled={locked || cantidadDeExtra(item) <= 1}
                                aria-label="-"
                                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
                              >
                                <Minus size={12} />
                              </button>
                              <span className="min-w-[5.5rem] text-center whitespace-nowrap">
                                {deLabel(cantidadDeExtra(item), people)}
                              </span>
                              <button
                                type="button"
                                onClick={() => ajustarCantidadExtra(item, 1)}
                                disabled={locked || cantidadDeExtra(item) >= people}
                                aria-label="+"
                                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
                              >
                                <Plus size={12} />
                              </button>
                            </span>
                          </div>
                        )}
                    </div>
                  ))}
                </div>

                {/* Divulgacion progresiva en linea: el control de cada opcion
                    vive DENTRO de su propia tarjeta y se abre ahi mismo. Antes
                    el select se pintaba despues del grupo entero, asi que
                    aparecia al fondo, separado de la opcion que lo habia
                    revelado — no habia forma de ver a cual pertenecia. */}
                <fieldset className="mt-5 border-t border-border pt-5" disabled={locked}>
                  <legend className="sr-only">{checkout.transporte.headline}</legend>
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">
                      {checkout.transporte.headline}
                    </p>
                    {/* El precio del traslado elegido, arriba y a la derecha:
                        alineado con el patron del resto del checkout, donde el
                        monto siempre va del lado del renglon al que pertenece. */}
                    {transportePrecio?.monto != null && (
                      <span className="shrink-0 text-sm text-foreground">
                        {currency.format(Number(transportePrecio.monto))}
                      </span>
                    )}
                  </div>

                  <div className="mt-3 flex flex-col gap-2">
                    {opcionesTransporte.map((opcion) => {
                      const activa = transporteModo === opcion.valor;
                      return (
                        <div
                          key={opcion.valor}
                          className={`border transition-colors duration-200 ${
                            activa ? 'border-accent bg-surface' : 'border-border'
                          }`}
                        >
                          <label className="flex cursor-pointer items-center gap-3 px-4 py-3 text-sm text-foreground">
                            <input
                              type="radio"
                              name="transporte-modo"
                              checked={activa}
                              onChange={() => setTransporteModo(opcion.valor)}
                              className="h-4 w-4 shrink-0 accent-accent"
                            />
                            <span className="flex-1">{opcion.etiqueta}</span>
                          </label>

                          {/* `initial={false}`: la tarjeta ya abierta al reponer
                              un checkout no debe animarse como si el cliente
                              acabara de elegirla. */}
                          <AnimatePresence initial={false}>
                            {activa && opcion.panel && (
                              <motion.div
                                key="panel"
                                initial={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }}
                                animate={
                                  sinMovimiento ? { opacity: 1 } : { height: 'auto', opacity: 1 }
                                }
                                exit={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }}
                                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                                className="overflow-hidden"
                              >
                                <div className="border-t border-border px-4 py-3">{opcion.panel}</div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </div>

                  {/* Solo importa para el recargo de grupo (el precio base no
                      escala por persona, ver apps/payments/pricing.py): quien
                      no sube a la camioneta no debe contarse para alcanzarlo.
                      El precio de arriba sigue siendo el del catalogo para el
                      grupo completo — la nota de abajo evita que se lea como
                      definitivo. */}
                  {transporteModo !== 'ninguno' && people > 1 && (
                    <div className="mt-3 flex flex-col gap-1 border-t border-border pt-3">
                      <div className="flex items-center justify-between gap-3 text-sm text-foreground">
                        <span className="text-muted">{checkout.transportQuantity.question}</span>
                        <span className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => ajustarPersonasTransporte(-1)}
                            disabled={locked || personasTransporteEfectivo <= 1}
                            aria-label="-"
                            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
                          >
                            <Minus size={12} />
                          </button>
                          <span className="min-w-[5.5rem] text-center whitespace-nowrap">
                            {deLabel(personasTransporteEfectivo, people)}
                          </span>
                          <button
                            type="button"
                            onClick={() => ajustarPersonasTransporte(1)}
                            disabled={locked || personasTransporteEfectivo >= people}
                            aria-label="+"
                            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
                          >
                            <Plus size={12} />
                          </button>
                        </span>
                      </div>
                      <p className="text-xs text-muted">{checkout.transportQuantity.finalPriceNote}</p>
                    </div>
                  )}
                </fieldset>

                {(!extrasConfirmado || pasoEditando === 3) && (
                  <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm font-medium text-foreground">{checkout.extrasConfirmQuestion}</p>
                    <button
                      type="button"
                      onClick={() => {
                        setExtrasConfirmado(true);
                        if (pasoEditando === 3) setPasoEditando(null);
                        setTimeout(() => {
                          refStripePanel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        }, 80);
                      }}
                      className="flex items-center justify-center gap-2 bg-action px-6 py-3 text-sm font-semibold text-action-foreground shadow-sm transition-transform active:scale-[0.98]"
                    >
                      <span>{checkout.continueToPayment || checkout.confirmStep}</span>
                      <ArrowRight size={16} weight="bold" />
                    </button>
                  </div>
                )}
              </CheckoutSectionCard>
            </motion.div>
          )}
        </div>

        {/* Ya no es `sticky`: se queda donde cae en su columna, no persigue el
            scroll. */}
        <div className="min-w-0">
          {/* Un solo StripePanel en todo el arbol — montarlo dos veces (uno por
              breakpoint) inicializaria Stripe.js y el widget de Turnstile por
              duplicado. En escritorio se ve siempre, en su propia columna: ahi
              nunca compite por el mismo canal de atencion que el formulario. En
              movil, donde SI comparte canal con los pasos, solo se ve completo
              hasta que el paso 3 (extras) se confirma con su propio boton —
              antes de eso queda montado pero oculto, nunca se desmonta ni se
              vuelve a armar. */}
          <div ref={refStripePanel} className={`scroll-mt-28 ${!extrasConfirmado ? 'hidden lg:block' : undefined}`}>
            <StripePanel
              lang={lang}
              checkout={checkout}
              waiverAccepted={waiverAccepted}
              onWaiverChange={setWaiverAccepted}
              lines={lines}
              total={total === null ? '—' : currency.format(total)}
              amountDueNow={amountDueNow === null ? '—' : currency.format(amountDueNow)}
              moneda={moneda}
              onMonedaChange={setMoneda}
              usdDisponible={usdDisponible}
              formaPago={formaPago}
              onFormaPagoChange={setFormaPago}
              codigoPromocional={codigoPromocional}
              onCodigoPromocionalChange={onCodigoPromocionalChange}
              promoEstado={promoEstado}
              promoPorcentaje={promoPorcentaje}
              phase={phase}
              error={error}
              pago={pago}
              feedback={dict.feedback}
              ayudaMensaje={ayudaMensaje}
              onSubmit={iniciarPago}
              onPagoConfirmado={(procesando) => {
                setPagoProcesando(procesando);
                setPhase('confirmed');
              }}
              onCaptchaToken={(token) => (captchaToken.current = token)}
            />
            {/* Fuera de la tarjeta de resumen, debajo: no es parte del desglose de
                precio, es la respuesta a "es seguro pagar aqui" y a "que pasa si
                no puedo ir por el clima" — las dos dudas que quedan justo antes
                de tocar pagar, y que si solo viven en el FAQ nadie las ve desde
                aqui. */}
            <p className="mt-4 text-xs leading-relaxed text-muted">
              {checkout.securityNoteBefore}
              <a
                href="https://stripe.com"
                target="_blank"
                rel="noopener"
                className="text-foreground underline underline-offset-2"
              >
                Stripe
              </a>
              {checkout.securityNoteAfter}
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">{checkout.refundNote}</p>
          </div>

          {/* Movil, mientras faltan los extras por confirmar: una franja con el
              total en vez de la tarjeta completa. No es que "no haya nada" —
              el total sigue a la vista todo el tiempo, solo que no compite con
              el paso que se esta llenando ahora mismo. */}
          {!extrasConfirmado && (
            <motion.div
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className="flex items-center justify-between border border-border bg-background px-5 py-4 lg:hidden"
            >
              <span className="text-sm text-muted">{checkout.total}</span>
              <span className="flex items-center gap-2 text-base font-medium text-foreground">
                {total === null ? '—' : currency.format(total)}
                <Lock size={14} weight="bold" className="text-muted" />
              </span>
            </motion.div>
          )}
        </div>
      </main>

      <CheckoutFooter lang={lang} footer={dict.footer} nav={nav} />

      <AnimatePresence>
        {recordatorioAbierto && (
          <AmenitiesReminder
            key="amenities-reminder"
            checkout={checkout}
            pendientes={extrasPendientes}
            onSeleccionarExtra={(id) => alternarExtra(id, true)}
            transportePendiente={transportePendiente}
            onContinuar={enviar}
            onCerrar={() => setRecordatorioAbierto(false)}
            enviando={enviando}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
