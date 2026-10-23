'use client';

import { useCallback, useEffect, useMemo, useRef, useState, useLayoutEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useBorrador } from '@/components/checkout/use-borrador';
import { useCorregir } from '@/components/checkout/use-corregir';
import { usePasoUrl } from '@/components/checkout/use-paso-url';
import { destinoDeError } from '@/lib/campo-paso';
import { validarTodo } from '@/lib/validar-reserva';
import { claveBorrador } from '@/lib/borrador-reserva';
import { pasoDeQuery } from '@/lib/paso-url';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { ConfirmacionReserva } from '@/components/confirmacion-reserva';
import { colorDeServicio } from '@/lib/color-actividad';
import { AyudaFlotante } from '@/components/checkout/ayuda-flotante';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { AvisoAccion } from '@/components/ui/aviso-accion';
import { problemaDe } from '@/lib/problema-reserva';
import { tieneWhatsapp } from '@/lib/contacto';
import { EncabezadoCompra } from '@/components/checkout/encabezado-compra';
import { ItemPaso } from '@/components/checkout/item-paso';
import { ReservaPlegable } from '@/components/pedido/reserva-plegable';
import { ProveedorCambioPrecio } from '@/components/checkout/cambio-precio';
import { PaginaCheckout } from '@/components/checkout/pagina-checkout';
import { AsistenteMovil } from '@/components/reserva/asistente-movil';
import { useMovil } from '@/components/reserva/use-movil';
import { usePantallaMovil } from '@/components/reserva/use-pantalla-movil';
import { anterior as pantallaAnterior, pantallasDe, primeraDelPaso } from '@/lib/pantallas-checkout';
import { useAyudaContextual } from '@/components/checkout/use-ayuda-contextual';
import { useScrollAlFoco } from '@/components/checkout/use-scroll-al-foco';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { BloqueContacto } from '@/components/checkout/bloques/bloque-contacto';
import { BloqueExtras } from '@/components/checkout/bloques/bloque-extras';
import { BloquePago, BloqueTarjetaPago } from '@/components/checkout/bloques/bloque-pago';
import { textoRegla, type ReglaPersonas } from '@/lib/regla-personas';
import { BloqueViaje } from '@/components/checkout/bloques/bloque-viaje';
import { formatDay } from '@/components/checkout/formato-dia';
import { precargarFormularioPago } from '@/components/checkout/pago/pago-diferido';
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
import { formatHour, fromLocalISODate, getTopePersonas, toLocalISODate } from '@/lib/dates';
import { controlDeFecha } from '@/lib/control-fecha';
import { conIva, porcentajeIva } from '@/lib/iva';
import type { SeleccionFechas } from '@/components/ui/calendario/calendario';
import { horasConAnticipacion } from '@/lib/anticipacion';
import { horasDeServicio } from '@/lib/horario-servicio';
import { mensajeDeAyuda, mensajeDeError } from '@/lib/errores';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import {
  cantidadEfectiva,
  erroresPersonalizaciones,
  seleccionInicial,
  totalPersonalizaciones,
  type SeleccionPersonalizacion,
} from '@/lib/personalizaciones';
import {
  estadoDeTarjeta, estadoVisible, numeroDePaso, pasoAnterior, unidaConAnterior, type EstadoTarjeta, type EstadoVisible, type PasoId,
  rotuloDePaso,
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

  // Id nuevo: una reserva cancelada ya no la reutiliza el upsert (solo reusa
  // pendiente_pago), asi que volver a intentar tras una cancelacion necesita uno limpio.
  const renovar = useCallback(() => {
    const nuevo = crypto.randomUUID();
    window.sessionStorage.setItem(CLAVE_CHECKOUT_ID, nuevo);
    setValue({ id: nuevo, recuperable: false });
  }, []);

  return [value, renovar] as const;
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
  // `true` si el enlace traia `day` pero se descarto y se uso la primera fecha disponible.
  fechaDescartada?: boolean;
  empresaSlug?: string;
  servicioId?: number | string | null;
  servicioNombre?: string | null;
  /** Origen de «salir» en el primer paso (`lib/origen.ts`), ya con idioma. */
  volverHref: string;
  /** `{ nombre, logo }` de la empresa del servicio (de `content/empresas`, server-only). */
  empresa?: { nombre: string; logo?: string; simbolo?: string };
  servicio?: ServicioCatalogo | null;
};

// 'recuperando': solo se pasa por aqui si esta pestana ya tenia un checkout_id
// guardado (ver useCheckoutId) — se pregunta si tiene una reserva detras antes
// de decidir si el checkout arranca vacio, precargado, o directo en la
// confirmacion.
// 'confirmando': stripe.confirmPayment() termino; se consulta getEstadoReserva hasta saber.
// 'cancelada': el webhook cancelo la reserva (reembolso); se muestra aviso y boton de elegir otra fecha.
type Phase = 'recuperando' | 'form' | 'submitting' | 'payment' | 'confirmed' | 'unavailable' | 'error' | 'confirmando' | 'cancelada';

type CampoContacto = 'fullName' | 'phone' | 'email';

/**
 * Orden en que se busca el primer campo malo para mandarle el foco. Es el orden
 * visual del formulario, no el de validacion: mandar el foco a un campo que esta
 * mas arriba de otro que tambien fallo desorienta.
 */
const ORDEN_CAMPOS: CampoContacto[] = ['phone', 'fullName', 'email'];

export function CheckoutView({
  lang,
  dict,
  initialDay,
  initialTime,
  initialPeople,
  minDate,
  queryOverride,
  fechaDescartada = false,
  empresaSlug,
  servicioId,
  servicioNombre,
  volverHref,
  empresa,
  servicio,
}: CheckoutViewProps) {
  const { checkout, booking } = dict;
  // null mientras sessionStorage todavia no se ha leido (solo dura hasta el
  // primer useLayoutEffect del cliente — ver useCheckoutId).
  const [checkoutIdValue, renovarCheckoutId] = useCheckoutId();
  const checkoutId = checkoutIdValue?.id ?? '';
  const recuperable = checkoutIdValue?.recuperable ?? false;
  const catalogoUnificado = servicio?.personalizaciones ?? [];
  const pideHora = servicio ? servicio.pide_hora : true;
  const horasDelServicio = useMemo(() => (servicio ? horasDeServicio(servicio) : []), [servicio]);

  // `null` = el cliente borró la fecha: Continuar la pide (no se repone sola).
  const [day, setDay] = useState<string | null>(initialDay);
  const [horaElegida, setTime] = useState(initialTime);
  // Anticipación mínima: de las horas del servicio, solo las que ese día aún cumplen. «Ahora» se fija al montar.
  const [ahoraDeCarga] = useState(() => new Date());
  const horasDisponibles = useMemo(
    () => (day ? horasConAnticipacion(day, horasDelServicio, ahoraDeCarga) : horasDelServicio),
    [day, horasDelServicio, ahoraDeCarga],
  );
  // Al cambiar de día, una hora que dejó de cumplir la anticipación pasa a la primera que sí.
  const time = horasDisponibles.includes(horaElegida) ? horaElegida : (horasDisponibles[0] ?? horaElegida);
  const topePersonas = getTopePersonas(servicio?.capacidad_maxima);
  const [people, setPeople] = useState(() => Math.min(initialPeople, topePersonas));
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
    if (!day) return null;
    const d = fromLocalISODate(day);
    d.setDate(d.getDate() + 1);
    return toLocalISODate(d);
  }, [day]);
  const fechaSalida = day && fechaSalidaManual && fechaSalidaManual > day ? fechaSalidaManual : defaultFechaSalida;

  const estrategiaCupo = servicio?.estrategia_cupo ?? 'por_recurso_dia';
  const tieneHospedaje = estrategiaCupo === 'por_noche';
  // El cupo por día (`/cupo/` y `/cupo/rango/`) contesta por las pangas: solo vale para la pesca.
  // Hospedaje y bajo demanda se validan al pagar.
  const conCupo = estrategiaCupo === 'por_recurso_dia';
  const { control: controlFecha } = controlDeFecha({ tipo: 'servicio', estrategia_cupo: estrategiaCupo, pide_hora: pideHora });
  const [errorFecha, setErrorFecha] = useState('');
  const elegirFechas = ({ desde, hasta }: SeleccionFechas) => {
    setDay(desde);
    setFechaSalidaManual(hasta);
    if (desde) setErrorFecha('');
  };

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
  // Donde se pinta la tarjeta "Cómo pagas" (el cuarto paso, en la columna de pasos).
  const [destinoTarjetaPago, setDestinoTarjetaPago] = useState<HTMLElement | null>(null);
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

  // Una sola vez: el enlace traia una fecha que no sirvio y se uso otra. Se espera a que el
  // formulario este listo y solo se avisa si sigue vigente (una reserva recuperada puede traer su fecha).
  const avisoFechaMostrado = useRef(false);
  useEffect(() => {
    if (!fechaDescartada || avisoFechaMostrado.current || phase !== 'form') return;
    avisoFechaMostrado.current = true;
    if (day !== initialDay) return;
    avisar('info', dict.feedback.dateChanged.replace('{date}', formatDay(fromLocalISODate(initialDay), lang)));
  }, [fechaDescartada, phase, day, initialDay, avisar, dict.feedback.dateChanged, lang]);
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
  const [recuperadoIva, setRecuperadoIva] = useState<number | null>(null);
  const [pago, setPago] = useState<Pago | null>(null);
  /** ISO 8601 del vencimiento del apartado devuelto por el ultimo crear-pago exitoso. null = sin apartado. */
  const [apartadoHasta, setApartadoHasta] = useState<string | null>(null);
  /** Tras ~12 s sin respuesta, «confirmando» pasa a «seguimos confirmando». */
  const [confirmandoLargo, setConfirmandoLargo] = useState(false);
  /** Cambia para remontar StripePanel y con el el widget de Turnstile (token de un solo uso). */
  const [captchaKey, setCaptchaKey] = useState(0);
  const [codigoPromocional, setCodigoPromocional] = useState('');
  const [promoEstado, setPromoEstado] = useState<'idle' | 'verificando' | 'valido' | 'invalido'>(
    'idle',
  );
  const [promoPorcentaje, setPromoPorcentaje] = useState<string | null>(null);
  // Lo que resta el codigo segun el servidor (misma funcion que `crear-pago`).
  const [promoDescuento, setPromoDescuento] = useState<{ valor: number; base: number | null } | null>(null);
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
    if (!day || !conCupo) return;

    (async () => {
      let cupo;
      try {
        cupo = await getCupo(day, people, empresaSlug, checkoutId || undefined);
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
  }, [day, conCupo, people, lang, checkout.dayFullOffer, checkout.noBoatForGroupNotice, empresaSlug, checkoutId]);

  const promoCheckId = useRef(0);

  // El estado deriva del tecleo mismo (idle/verificando), aqui en el handler y
  // no en el efecto de abajo: poner un setState sincrono en el cuerpo de un
  // efecto dispara un render en cascada. El efecto solo hace lo que si
  // necesita esperar — la llamada de red con debounce.
  const onCodigoPromocionalChange = (value: string) => {
    setCodigoPromocional(value);
    setPromoEstado(value.trim() ? 'verificando' : 'idle');
    if (!value.trim()) {
      setPromoPorcentaje(null);
      setPromoDescuento(null);
    }
  };


  const usdDisponible = Number(servicio?.tipo_cambio_usd) > 0;
  // Hospedaje `por_noche`: la misma estrategia del servidor (`PorNoche`), precio × noches, sin
  // cargo por persona. Es vista previa hasta crear el pago (el resumen dice «Estimado»).
  const precioPorNoche = servicio?.estrategia_precio === 'por_noche';
  const nochesHospedaje = day && fechaSalida
    ? Math.max(1, Math.round((fromLocalISODate(fechaSalida).getTime() - fromLocalISODate(day).getTime()) / 86_400_000))
    : 1;
  const precioBase = servicio ? aMoneda(servicio.precio_base, moneda, servicio.tipo_cambio_usd) : null;
  const tourPrice = precioBase === null ? null : precioPorNoche ? precioBase * nochesHospedaje : precioBase;

  const currency = useMemo(
    () => new Intl.NumberFormat(intlLocale(lang), { style: 'currency', currency: moneda }),
    [lang, moneda],
  );
  // El monto con su moneda, para la píldora del cambio de precio y la regla por personas.
  const formatearCambio = useCallback((monto: number) => `${currency.format(monto)} ${moneda}`, [currency, moneda]);

  // El precio es por viaje (la reserva es de la embarcacion completa), pero
  // pasando de las personas incluidas se suma un cargo por cada una. El servidor
  // recalcula esto mismo al crear el pago: aqui solo se muestra.
  const personasIncluidas = servicio?.personas_incluidas ?? 0;
  const precioPersonaExtra = servicio
    ? aMoneda(servicio.precio_persona_extra, moneda, servicio.tipo_cambio_usd) ?? 0
    : 0;
  const personasExtra = Math.max(0, people - personasIncluidas);
  const cargoPersonas = precioPorNoche ? 0 : personasExtra * (precioPersonaExtra || 0);

  const cargoPersonalizacionesServicio = totalPersonalizaciones(
    catalogoUnificado, personalizaciones, people, moneda, servicio?.tipo_cambio_usd ?? '',
  );

  const subtotalSinDescuento = tourPrice === null || cargoPersonalizacionesServicio === null
    ? null
    : tourPrice + cargoPersonas + cargoPersonalizacionesServicio;

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
        resultado = await validarCodigoPromocional(codigo, contact.email, empresaSlug, subtotalSinDescuento);
      } catch {
        if (promoCheckId.current === checkId) setPromoEstado('idle');
        return;
      }
      if (promoCheckId.current !== checkId) return;

      if (resultado.valido) {
        setPromoEstado('valido');
        setPromoPorcentaje(resultado.porcentaje_descuento);
        setPromoDescuento(resultado.descuento === null ? null : { valor: Number(resultado.descuento), base: subtotalSinDescuento });
      } else {
        setPromoEstado('invalido');
        setPromoPorcentaje(null);
        setPromoDescuento(null);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [codigoPromocional, contact.email, empresaSlug, subtotalSinDescuento]);

  // Solo informativo (redondeo igual al de `cargo_por_descuento` en
  // apps/payments/pricing.py): el monto real lo congela `crear-pago` sobre el
  // subtotal exacto, este puede diferir por centavos de redondeo.
  const descuentoPromocional =
    subtotalSinDescuento !== null && promoEstado === 'valido' && promoPorcentaje
      ? Math.min(
          subtotalSinDescuento,
          promoDescuento && promoDescuento.base === subtotalSinDescuento
            ? promoDescuento.valor
            : Math.round(subtotalSinDescuento * (Number(promoPorcentaje) / 100) * 100) / 100,
        )
      : 0;

  // El IVA se suma al final, sobre el precio ya con descuento; el anticipo se calcula sobre este total.
  const netoSinIva = subtotalSinDescuento === null ? null : subtotalSinDescuento - descuentoPromocional;
  const { iva: ivaEstimado, total: totalConIva } = netoSinIva === null
    ? { iva: 0, total: null }
    : conIva(netoSinIva);
  const lineaIva = (monto: number) => ({
    label: `${checkout.ivaLabel} (${porcentajeIva()} %)`,
    amount: currency.format(monto),
  });

  /**
   * Las lineas de lo que se compro aparte del viaje (mas el descuento y el
   * IVA, si aplican). Se arman una sola vez y las usan los dos lugares que las
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
    ...(ivaEstimado > 0 ? [lineaIva(ivaEstimado)] : []),
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
    ...(recuperadoIva !== null && recuperadoIva > 0 ? [lineaIva(recuperadoIva)] : []),
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

  const total = totalConIva;
  const amountDueNow =
    total === null
      ? null
      : formaPagoEfectiva === 'anticipo' && servicio
        ? Math.round(total * (servicio.porcentaje_anticipo / 100) * 100) / 100
        : total;

  const diaTexto = day ? formatDay(fromLocalISODate(day), lang) : checkout.calendario.sinFecha;
  const salidaTexto = fechaSalida ? formatDay(fromLocalISODate(fechaSalida), lang) : '';

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

  // Borrador de la pestaña y paso en la URL (ver `use-borrador` y `use-paso-url`). Solo se repone
  // un borrador si la URL ya trae `?paso=`: una entrada nueva desde el sitio manda sobre uno viejo.
  const reponerBorrador = useSearchParams().get('paso') !== null;
  const claveDelBorrador = claveBorrador('reservar', servicio?.slug ?? servicioNombre ?? 'servicio');
  const borradorListo = useBorrador({
    clave: claveDelBorrador,
    habilitado: phase !== 'recuperando',
    reponer: reponerBorrador,
    terminado: phase === 'confirmed',
    estado: { day, time, people, personalizaciones, fechaSalidaManual, moneda, formaPago, contact, paso: actual },
    restaurar: (guardado) => {
      // Una reserva recuperada del servidor ya llevó al cliente a Pago: manda sobre el borrador.
      if (actual === 'pago') return;
      setDay(guardado.day);
      setTime(guardado.time);
      setPeople(guardado.people);
      setPersonalizaciones(guardado.personalizaciones);
      setFechaSalidaManual(guardado.fechaSalidaManual);
      setMoneda(guardado.moneda);
      setFormaPago(guardado.formaPago);
      setContact(guardado.contact);
      setActual(pasoDeQuery(guardado.paso) ?? 'viaje');
    },
  });
  const pagoEnCurso = phase === 'payment' || phase === 'submitting' || phase === 'confirmando';

  // Móvil (< 640 px): asistente de una pantalla por vez en lugar de tarjetas (ver `pantallas-checkout`).
  // Las respuestas viven en el mismo estado; el asistente solo decide qué pantalla se ve.
  const movil = useMovil();
  const tieneExtras = catalogoUnificado.length > 0;
  const pantallas = useMemo(() => pantallasDe({ tipo: 'servicio', tieneExtras }), [tieneExtras]);
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
    (destino: { paso: PasoId; campo: string }) =>
      irA(destino.campo.startsWith('personalizacion-') ? 'extras' : primeraDelPaso(pantallas, destino.paso)),
    [irA, pantallas],
  );
  const corregir = useCorregir(actual, setEditando, movil ? irAPantallaDelCampo : undefined);
  usePasoUrl({ actual, editando, setEditando, bloqueado: pagoEnCurso, habilitado: borradorListo && !movil });
  // Lo que en escritorio reabre una tarjeta (sin cupo, elegir otra fecha) en móvil lleva a su pantalla.
  const reabrirPaso = (paso: PasoId) => {
    if (movil) irA(primeraDelPaso(pantallas, paso));
    else setEditando(paso);
  };
  // Una sola flecha: «paso anterior» mientras haya uno y no haya un pago en curso; si no, sale al origen.
  const pasoVisible = editando ?? actual;
  const alPasoAnterior = pagoEnCurso
    ? undefined
    : movil
      ? pantallaAnterior(pantallas, asistente.pantalla.id) !== null ? () => { asistente.retroceder(); } : undefined
      : pasoAnterior(pasoVisible) !== null ? () => setEditando(pasoAnterior(pasoVisible)) : undefined;

  // Al llegar a "Cómo pagas" se pide ya el formulario de tarjeta (y con él Stripe.js):
  // para cuando se crea el pago, el chunk está listo. Solo en el cliente.
  useEffect(() => {
    if (actual === 'pago') precargarFormularioPago().catch(() => {});
  }, [actual]);

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
        setRecuperadoIva(estado.iva !== null ? Number(estado.iva) : null);
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
  const confirmarContacto = (): boolean => {
    const errores = validarContacto();
    setErroresCampo(errores);

    if (Object.keys(errores).length > 0) {
      ayuda.tropezar('validacion');
      const primero = ORDEN_CAMPOS.find((campo) => errores[campo]);
      if (primero) refsContacto[primero].current?.focus();
      return false;
    }

    continuarAPago();
    return true;
  };

  /** Viaje incluye los extras: no se avanza con un extra obligatorio sin contestar. */
  /** Sin fecha no se sale de Viaje: el error queda pegado al calendario. */
  const validarFecha = (): boolean => {
    if (day) return true;
    ayuda.tropezar('validacion');
    setErrorFecha(checkout.calendario.faltaFecha);
    return false;
  };

  const confirmarViaje = (): boolean => {
    if (!validarFecha()) return false;
    const erroresDePersonalizacion = erroresPersonalizaciones(catalogoUnificado, personalizaciones);
    setErroresPersonalizacion(erroresDePersonalizacion);
    const primera = catalogoUnificado.find((p) => erroresDePersonalizacion[p.id]);
    if (primera) {
      ayuda.tropezar('validacion');
      const campo = document.getElementById(`personalizacion-${primera.id}`);
      campo?.focus();
      campo?.scrollIntoView({ block: 'center' });
      return false;
    }
    setActual((a) => (a === 'viaje' ? 'datos' : a));
    setEditando(null);
    return true;
  };

  /** Datos confirmados: pasa al pago y lo trae a la vista (en móvil el panel de pago aparece aquí). */
  function continuarAPago() {
    setActual('pago');
    setEditando(null);
    // En móvil el asistente ya sube a la pantalla nueva; el panel del pedido no está a la vista.
    if (movil) return;
    setTimeout(() => {
      refStripePanel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  }

  /** Primer paso del pago: valida, y antes de tocar la red ofrece las amenidades. */
  const iniciarPago = () => {
    // Todo lo que impide pagar se revisa junto y se lleva al cliente al primero, en su paso y
    // en su campo: una tarjeta ya confirmada está plegada y un campo que no está montado no
    // recibe foco.
    const errores = validarContacto();
    setErroresCampo(errores);
    const erroresDePersonalizacion = erroresPersonalizaciones(catalogoUnificado, personalizaciones);
    setErroresPersonalizacion(erroresDePersonalizacion);
    const primeraPersonalizacion = catalogoUnificado.find((p) => erroresDePersonalizacion[p.id]);
    const primerContacto = ORDEN_CAMPOS.find((campo) => errores[campo]);
    if (!day) setErrorFecha(checkout.calendario.faltaFecha);
    const problema = validarTodo([
      day ? null : { paso: 'viaje', campo: 'checkout-error-fecha', mensaje: checkout.calendario.faltaFecha },
      primeraPersonalizacion
        ? { paso: 'viaje', campo: `personalizacion-${primeraPersonalizacion.id}`, mensaje: erroresDePersonalizacion[primeraPersonalizacion.id] }
        : null,
      primerContacto ? { paso: 'datos', campo: `checkout-error-${primerContacto}`, mensaje: errores[primerContacto] ?? '' } : null,
    ]);
    if (problema) {
      ayuda.tropezar('validacion');
      corregir(problema);
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

    enviar();
  };

  /**
   * Unico punto que toca la red. Se protege contra envios repetidos con la
   * fase: mientras esta en `submitting` no vuelve a entrar, y la reserva se
   * guarda con `checkout_id`, asi que reintentar tras un error reescribe la
   * misma fila en vez de crear otra.
   */
  /**
   * El ultimo lugar se fue mientras el cliente llenaba o pagaba: vuelve al paso del
   * viaje con todo lo capturado en memoria y el aviso de cupo agotado (mas la fecha
   * alternativa si el servidor la dio). La reserva sigue pendiente_pago y al reenviar
   * se reutiliza por checkout_id.
   */
  const volverPorSinCupo = (body: Record<string, unknown>) => {
    const motivo = body['motivo'] as string | undefined;
    const proximaDisponible = body['proxima_disponible'] as string | null | undefined;
    const plantilla =
      motivo === 'sin_panga' || motivo === 'sin_lugar'
        ? checkout.noBoatForGroupNotice
        : checkout.dayFullOffer;
    const mensajeDia = plantilla
      .replace('{date}', diaTexto)
      .replace('{people}', String(people));
    setSinLugar({
      mensaje: `${checkout.cupoAgotado} ${mensajeDia}`,
      alternativa: proximaDisponible ?? null,
    });
    setPago(null);
    setApartadoHasta(null);
    setActual('viaje');
    reabrirPaso('viaje');
    setPhase('form');
  };

  const enviar = async () => {
    if (phase === 'submitting' || phase === 'payment') return;
    if (!day) return;

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
        fecha_salida: tieneHospedaje ? fechaSalida ?? undefined : undefined,
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
      setApartadoHasta(pagoResponse.apartado_hasta);
      setPhase('payment');
      // Creado el pago, el asistente móvil pasa a la tarjeta.
      if (movil) irA('tarjeta-0');
      // La reserva ya quedo guardada aunque el pago siga pendiente: decirlo
      // separa los dos pasos, para que un fallo de tarjeta no se lea como
      // "se perdio todo lo que llene".
      avisar('exito', dict.feedback.saved);
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.detail as Record<string, unknown> | null;
        const codigo = body && typeof body === 'object' ? (body['codigo'] as string | undefined) : undefined;

        // sin_cupo: volver al paso del viaje con datos en memoria y aviso de cupo agotado.
        // El cliente ya tiene una reserva guardada (pendiente_pago); reenviarla la reutiliza.
        if (codigo === 'sin_cupo') {
          volverPorSinCupo(body ?? {});
          return;
        }

        // pago_en_curso / ya_no_pendiente: el cobro ya esta activo o la reserva
        // cambio de estado. Pasar directo al polling sin llamar a confirmPayment.
        if (codigo === 'pago_en_curso' || codigo === 'ya_no_pendiente') {
          setPhase('confirmando');
          return;
        }

        // reintentar (503 candado): no es un error de pagos sino un reintento suave.
        // El cliente se queda en el formulario de pago con el aviso.
        if (codigo === 'reintentar') {
          setError(dict.feedback.reintentar);
          setPhase('error');
          return;
        }

        if (err.status === 503) {
          setPhase('unavailable');
          return;
        }

        // El codigo paso la validacion en vivo pero crear-pago lo rechazo con el
        // subtotal real (se agoto justo ahora, o vencio mientras el cliente
        // llenaba el formulario). Se marca invalido para que reintentar sin el
        // codigo funcione al primer intento, en vez de repetir el mismo 400.
        if (err.status === 400 && promoEstado === 'valido') {
          setPromoEstado('invalido');
          setError(checkout.promoCode.invalid);
          setPhase('error');
          return;
        }

        // El servidor rechazó un campo concreto: se lleva al cliente a su paso y a su control.
        if (err.status === 400) {
          const destino = destinoDeError(err.detail, 'checkout');
          if (destino) {
            setError(mensajeDeError(err, checkout, dict.feedback));
            setPhase('error');
            corregir(destino);
            return;
          }
        }
      }
      setError(mensajeDeError(err, checkout, dict.feedback));
      setPhase('error');
    }
  };

  /**
   * Se llama en CADA clic de «Pagar», antes de hablar con Stripe: renueva el apartado.
   * Reenvia identicos forma_pago y codigo_promocional (si no, el servidor tomaria
   * «completo» y sin codigo y cambiaria el monto del cobro). null = cobrar; texto =
   * no cobrar y mostrarlo; '' = no cobrar, esta funcion ya cambio de pantalla.
   */
  const antesDePagar = async (): Promise<string | null> => {
    if (reservaId === null || !pago) return null;
    try {
      const renovado = await crearPago(reservaId, {
        checkout_id: checkoutId,
        forma_pago: formaPagoEfectiva,
        codigo_promocional:
          promoEstado === 'valido' ? codigoPromocional.trim().toUpperCase() : undefined,
      }, empresaSlug);
      setApartadoHasta(renovado.apartado_hasta);
      if (Number(renovado.monto_a_cobrar) !== Number(pago.monto_a_cobrar)) {
        // El cliente vio otro importe: no se le cobra sin que lo vea. Al pulsar
        // Pagar de nuevo el importe ya coincide y sigue.
        setPago(renovado);
        return checkout.montoDistinto.replace(
          '{monto}',
          currency.format(Number(renovado.monto_a_cobrar)),
        );
      }
      return null;
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.detail as Record<string, unknown> | null;
        const codigo = body && typeof body === 'object' ? body['codigo'] : undefined;
        if (codigo === 'sin_cupo') {
          volverPorSinCupo(body ?? {});
          return '';
        }
        if (codigo === 'pago_en_curso' || codigo === 'ya_no_pendiente') {
          setPhase('confirmando');
          return '';
        }
      }
      return mensajeDeError(err, checkout, dict.feedback);
    }
  };

  // Tras stripe.confirmPayment() el webhook aun puede cancelar y reembolsar si el
  // lugar se fue: se pregunta cada 2 s hasta saber, y no se dice «confirmada» antes.
  useEffect(() => {
    if (phase !== 'confirmando') return;
    let cancelado = false;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    const inicio = Date.now();
    const consultar = async () => {
      try {
        const estado = await getEstadoReserva(checkoutId, empresaSlug);
        if (cancelado) return;
        if (estado.estado === 'pagada') {
          setReservaId(estado.reserva_id);
          setPhase('confirmed');
          return;
        }
        if (estado.estado === 'cancelada') {
          setPhase('cancelada');
          return;
        }
      } catch {
        // Sin red o aun sin respuesta: se sigue preguntando.
      }
      if (cancelado) return;
      const transcurrido = Date.now() - inicio;
      if (transcurrido > 12000) setConfirmandoLargo(true);
      if (transcurrido > 600000) return;
      temporizador = setTimeout(consultar, transcurrido > 12000 ? 10000 : 2000);
    };
    consultar();
    return () => {
      cancelado = true;
      if (temporizador) clearTimeout(temporizador);
    };
  }, [phase, checkoutId, empresaSlug]);

  /** Tras una cancelacion: id nuevo, Turnstile nuevo y el formulario tal como lo dejo el cliente. */
  const elegirOtraFecha = () => {
    borrarPendiente(checkoutId);
    renovarCheckoutId();
    captchaToken.current = '';
    setCaptchaKey((k) => k + 1);
    setPago(null);
    setApartadoHasta(null);
    setReservaId(null);
    setPagoProcesando(false);
    setConfirmandoLargo(false);
    setError('');
    setSinLugar(null);
    setActual('viaje');
    reabrirPaso('viaje');
    setPhase('form');
  };

  const locked = phase === 'payment' || phase === 'unavailable';
  // Token de Turnstile. Lo produce el widget solo; el backend lo exige unicamente
  // al crear la reserva, asi que estar vacio no bloquea un reenvio.
  const captchaToken = useRef('');

  const horaTexto = pideHora && time ? formatHour(time) : '';
  const nombresExtras = catalogoUnificado
    .filter((p) => personalizacionesMap.has(p.id))
    .map((p) => p.nombre)
    .join(', ');
  // Una línea por dato, para leerlo al abrir el renglón cuando ya no se puede cambiar.
  const detallePaso1 = [
    { etiqueta: checkout.summary.date, valor: diaTexto },
    tieneHospedaje ? { etiqueta: checkout.summary.checkOut, valor: salidaTexto } : null,
    horaTexto ? { etiqueta: checkout.summary.time, valor: horaTexto } : null,
    { etiqueta: checkout.summary.people, valor: String(people) },
    nombresExtras ? { etiqueta: checkout.extrasStepHeadline, valor: nombresExtras } : null,
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);
  const detallePaso2 = [
    { etiqueta: checkout.fullName, valor: contact.fullName },
    { etiqueta: checkout.email, valor: contact.email },
    { etiqueta: checkout.phone, valor: contact.phone },
  ].filter((linea) => linea.valor.trim() !== '');

  // Lo que se le manda a la vendedora si el cliente usa la salida de emergencia
  // de un error. Lleva su fecha, hora y grupo para que ella no tenga que
  // preguntarlos y el no tenga que redactar nada ya estando frustrado.
  const ayudaMensaje = mensajeDeAyuda(pideHora ? dict.feedback.helpMessage : dict.feedback.helpMessageNoTime, {
    fecha: diaTexto,
    hora: horaTexto,
    personas: people,
  });

  // Se pregunta antes de pintar nada del formulario: si esta reserva ya se
  // pago, no tiene sentido mostrar un instante el paso 1 vacio para luego
  // reemplazarlo por la confirmacion.
  if (phase === 'recuperando') {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-2 bg-background px-6">
        <WaitNotice mensaje={dict.feedback.recoveringNotice} />
      </div>
    );
  }

  if (phase === 'confirmando') {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-2 bg-background px-6 text-center">
        <WaitNotice
          mensaje={confirmandoLargo ? checkout.siguiendoConfirmando : checkout.confirmandoTitulo}
        />
      </div>
    );
  }

  if (phase === 'cancelada') {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <h1 className="texto-subtitulo text-foreground">{checkout.lugarNoAseguradoTitulo}</h1>
        <p className="max-w-md text-sm text-foreground/80">{checkout.lugarNoAseguradoCuerpo}</p>
        <BotonPaso onClick={elegirOtraFecha}>{checkout.eligeOtraFecha}</BotonPaso>
      </div>
    );
  }

  if (phase === 'confirmed') {
    const pescaDeSalYSol = !servicio || (servicio.tipo_servicio === 'pesca' && servicio.empresa_slug === 'sal-y-sol');
    return (
      <ConfirmacionReserva
        lang={lang}
        dict={dict}
        datos={{
          // No-null: esta fase solo se alcanza despues de crearPago (pago fresco) o de recuperar una
          // reserva ya pagada por su checkout_id — las dos rutas ponen `reservaId` antes de llegar aqui.
          folio: reservaId!,
          // Un pago repuesto del servidor ya esta acreditado.
          procesando: recuperadoPagado !== null ? false : pagoProcesando,
          nombre: contact.fullName,
          email: contact.email,
          color: colorDeServicio(servicio ?? { tipo_servicio: 'pesca' }),
          titulo: servicio?.nombre ?? servicioNombre ?? checkout.tituloPagina,
          empresas: empresa ? [empresa.nombre] : [],
          fecha: diaTexto,
          lineas: [
            { etiqueta: checkout.summary.date, valor: diaTexto },
            tieneHospedaje ? { etiqueta: checkout.summary.checkOut, valor: salidaTexto } : null,
            horaTexto ? { etiqueta: checkout.summary.time, valor: horaTexto } : null,
            { etiqueta: checkout.summary.people, valor: String(people) },
          ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null),
          // Vacio en una reserva repuesta: `EstadoReservaView` solo devuelve el monto cobrado en la
          // rama `pagada`, no el desglose, y rearmarlo con el catalogo de hoy podria enseñar un precio
          // distinto del pagado.
          extras: recuperadoPagado !== null ? lineasExtrasRecuperadas : lineasExtras,
          // Un pago recuperado manda su propio monto (lo que Stripe cobro de verdad): el precio de hoy
          // o las amenidades en el estado local pueden no ser ya las mismas con las que se pago.
          pagado: recuperadoPagado !== null
            ? currency.format(recuperadoPagado)
            : amountDueNow === null
              ? null
              : currency.format(amountDueNow),
          saldoEnEfectivo: recuperadoPagado !== null
            ? recuperadoSaldo !== null && recuperadoSaldo > 0
              ? currency.format(recuperadoSaldo)
              : null
            : total !== null && amountDueNow !== null && total > amountDueNow
              ? currency.format(total - amountDueNow)
              : null,
          // El punto de encuentro y la lista de qué llevar solo existen para la pesca de Sal y Sol.
          encuentro: pescaDeSalYSol ? { lugar: `${dict.footer.address}, ${dict.footer.city}`, hora: horaTexto || undefined } : null,
          llevar: pescaDeSalYSol ? dict.included.bring : undefined,
        }}
      />
    );
  }

  // Un solo foco abierto: si el cliente reabrió una respuesta, la tarjeta activa
  // se pliega a un renglón "pendiente" hasta que termine de corregirla.
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

  // El stepper cuenta el pago como paso 3 en cuanto se confirman los datos, o
  // antes si ya se mandó el formulario (en escritorio el panel siempre está a la vista).
  const pasoActualStepper = movil
    ? numeroDePaso(asistente.pantalla.paso)
    : phase === 'submitting' || phase === 'payment' ? numeroDePaso('pago') : numeroDePaso(actual);
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

  // Qué cubre el precio y qué cuesta sumar a alguien, bajo el contador (cambia con el número).
  const regla: ReglaPersonas | null = servicio?.estrategia_precio === 'por_grupo'
    ? { tipo: 'grupo', incluidas: personasIncluidas, extra: precioPersonaExtra, maximo: topePersonas }
    : servicio?.estrategia_precio === 'por_persona' && precioBase !== null
      ? { tipo: 'persona', precio: precioBase }
      : null;
  const reglaPersonas = regla ? textoRegla(regla, people, formatearCambio, checkout.reglaPersonas) : null;

  const lineasViaje = [
    { etiqueta: checkout.summary.date, valor: diaTexto },
    tieneHospedaje ? { etiqueta: checkout.summary.checkOut, valor: salidaTexto } : null,
    horaTexto ? { etiqueta: checkout.summary.time, valor: horaTexto } : null,
    { etiqueta: checkout.summary.people, valor: String(people) },
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);

  // Los mismos bloques en las tarjetas de escritorio y en las pantallas del asistente móvil.
  const bloqueViaje = (
    <BloqueViaje
      lang={lang}
      checkout={checkout}
      booking={booking}
      locked={locked}
      day={day}
      minDate={minDate}
      control={controlFecha}
      onFechas={elegirFechas}
      conCupo={conCupo}
      bajoDemanda={estrategiaCupo === 'bajo_demanda'}
      empresaSlug={empresaSlug}
      errorFecha={errorFecha}
      pideHora={pideHora}
      time={time}
      horaTexto={horaTexto}
      horasDisponibles={horasDisponibles}
      onHora={setTime}
      people={people}
      maxPersonas={topePersonas}
      onPersonas={cambiarPersonas}
      onTopePersonas={() => ayuda.tropezar('tope-personas')}
      tieneHospedaje={tieneHospedaje}
      fechaSalida={fechaSalida}
      reglaPersonas={reglaPersonas}
    />
  );
  const bloqueExtras = (
    <BloqueExtras
      lang={lang}
      checkout={checkout}
      catalogo={catalogoUnificado}
      seleccionadas={personalizacionesMap}
      errores={erroresPersonalizacion}
      locked={locked}
      people={people}
      moneda={moneda}
      tipoCambioUsd={servicio?.tipo_cambio_usd}
      currency={currency}
      onAlternar={alternarPersonalizacion}
      onRespuesta={actualizarRespuestaPersonalizacion}
      onCantidad={ajustarCantidadPersonalizacion}
    />
  );
  const bloqueContacto = (
    <BloqueContacto
      idPrefijo="checkout"
      checkout={checkout}
      valores={contact}
      errores={erroresCampo}
      refs={{ phone: refPhone, fullName: refFullName, email: refEmail }}
      disabled={locked}
      onCambio={(campo, valor) => {
        setContact((prev) => ({ ...prev, [campo]: valor }));
        // El error se limpia al escribir: dejarlo puesto mientras el
        // cliente corrige lo convierte en un regaño que no se calla.
        if (erroresCampo[campo]) setErroresCampo((prev) => ({ ...prev, [campo]: undefined }));
      }}
    />
  );
  const bloqueTarjetaPago = (mostrarDestino: boolean, pagoEnCurso: Pago | null) => (
    <BloqueTarjetaPago
      lang={lang}
      checkout={checkout}
      feedback={dict.feedback}
      ayudaMensaje={ayudaMensaje}
      mostrarDestino={mostrarDestino}
      destinoRef={setDestinoTarjetaPago}
      pagoEnCurso={pagoEnCurso}
      apartadoHasta={apartadoHasta}
      antesDePagar={antesDePagar}
      onPagoConfirmado={(procesando) => {
        setPagoProcesando(procesando);
        setConfirmandoLargo(false);
        setPhase('confirmando');
      }}
    />
  );

  // Móvil: una pantalla por vez. «Cómo pagas» y la tarjeta traen su propio botón (el de la tarjeta
  // «Cómo pagas» llega a la barra por portal; el de Stripe, dentro del formulario).
  const pantalla = asistente.pantalla;
  const pantallaMovil = (() => {
    switch (pantalla.tipo) {
      case 'viaje':
        return { titulo: checkout.tripHeadline, contenido: bloqueViaje, accion: {
          etiqueta: checkout.barra.continuar,
          alPulsar: () => { if (tieneExtras ? validarFecha() : confirmarViaje()) asistente.avanzar(); },
        } };
      case 'extras':
        return { titulo: checkout.extrasStepHeadline, contenido: bloqueExtras, accion: {
          etiqueta: checkout.barra.continuar,
          alPulsar: () => { if (confirmarViaje()) asistente.avanzar(); },
        } };
      case 'contacto':
        return { titulo: checkout.stepper.datos, contenido: bloqueContacto, accion: {
          etiqueta: checkout.barra.continuar,
          alPulsar: () => { if (confirmarContacto()) asistente.avanzar(); },
        } };
      case 'como-pagas':
        return { titulo: checkout.howYouPay, contenido: bloqueTarjetaPago(true, null) };
      default:
        return { titulo: checkout.barra.tarjeta, contenido: bloqueTarjetaPago(false, phase === 'payment' ? pago : null), accion: {
          etiqueta: checkout.confirmPay, alPulsar: () => {}, deshabilitado: true, razon: checkout.barra.cargandoPago,
        } };
    }
  })();
  const nombrePaso = checkout.stepper[pantalla.paso];
  const asistenteMovil = (
    <AsistenteMovil
      id={pantalla.id}
      titulo={pantallaMovil.titulo}
      soloFundido={pantalla.paso === 'pago'}
      anuncio={`${rotuloDePaso(checkout.stepper.stepOf, pantalla.paso)}: ${nombrePaso}`}
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
        // Con lo que el cliente ya había contestado: `page.tsx` de la portada
        // lo lee y precarga el booking bar, para no hacerlo empezar de cero
        // solo por haber vuelto a revisar algo.
        volverHref={volverHref}
        alPasoAnterior={alPasoAnterior}
        empresa={empresa}
        empresasDeslinde={[empresaSlug ?? process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol']}
        volverLabel={checkout.back}
        encabezado={
          <EncabezadoCompra
            titulo={checkout.tituloPagina}
            detalle={servicioNombre || servicio?.nombre || undefined}
          />
        }
        aviso={sinLugar && day ? (
          <div className="mx-auto mb-2 max-w-6xl px-6 sm:px-8 lg:px-12">
            <AvisoAccion
              problema={problemaDe('sin_cupo', { tieneWhatsapp }, {
                ...checkout.problema,
                // La alternativa se OFRECE, no se aplica: el cliente decide si el siguiente día libre le sirve.
                sin_cupo: {
                  ...checkout.problema.sin_cupo,
                  cuerpo: sinLugar.mensaje,
                  accion: sinLugar.alternativa
                    ? checkout.takeOffered.replace('{date}', formatDay(fromLocalISODate(sinLugar.alternativa), lang))
                    : checkout.problema.sin_cupo.accion,
                },
              })}
              alAccionar={() => {
                const nueva = sinLugar.alternativa;
                if (!nueva) {
                  if (movil) irA('viaje');
                  else document.querySelector('[data-tarjeta-foco]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  return;
                }
                setDay(nueva);
                avisar('info', dict.feedback.dateChanged.replace('{date}', formatDay(fromLocalISODate(nueva), lang)));
              }}
            />
          </div>
        ) : undefined}
        stepper={stepperPago}
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
                detalle={detallePaso1}
                actionLabel={locked ? undefined : etiquetaAccion(crudoViaje)}
                onAction={locked || crudoViaje === 'activo' ? undefined : () => reabrir('viaje')}
                pie={crudoViaje === 'activo' && !locked
                  ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso>
                  : undefined}
              >
                <div className="flex flex-col gap-6">
                {bloqueViaje}
                {/* Los extras son parte del viaje. Bebidas se quitó del checkout: depende
                    del tipo de bebida, un dato que el sitio no captura; la vendedora la
                    sigue cotizando a mano. El punto de encuentro real y el aviso del
                    agente son información de después de pagar (BookingConfirmation). */}
                {bloqueExtras}
                </div>
              </CheckoutSectionCard>
            </ItemPaso>

            {estadoDatos && (
              <ItemPaso unida={unidaConAnterior(secuencia, 1)}>
                <CheckoutSectionCard
                  title={checkout.stepper.datos}
                  paso="datos"
                  estado={estadoDatos}
                  detalle={detallePaso2}
                  actionLabel={locked ? undefined : etiquetaAccion(crudoDatos)}
                  onAction={locked || crudoDatos === 'activo' ? undefined : () => reabrir('datos')}
                  pie={crudoDatos === 'activo' && !locked
                    ? <BotonPaso conFlecha onClick={confirmarContacto}>{checkout.continueToPayment || checkout.confirmStep}</BotonPaso>
                    : undefined}
                >
                  {bloqueContacto}
                </CheckoutSectionCard>
              </ItemPaso>
            )}

            </ReservaPlegable>

            {/* El cuarto paso. "Cómo pagas" se pinta aquí (portal del panel) al llegar al
                paso 4; el formulario de tarjeta aparece debajo cuando se crea el pago. */}
            {bloqueTarjetaPago(actual === 'pago' || phase !== 'form', phase === 'payment' ? pago : null)}
          </>
        )}
        pedido={
          // Un solo StripePanel en todo el arbol — montarlo dos veces inicializaria
          // Stripe.js y el widget de Turnstile por duplicado. En movil la zona de
          // pago se muestra al llegar al paso 4 (`pagoVisibleMovil`); antes queda
          // montada pero oculta, nunca se desmonta.
          <BloquePago
            key={captchaKey}
            refPanel={refStripePanel}
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
            nombreServicio={servicio?.nombre ?? servicioNombre}
            currency={currency}
            total={total}
            montoAhora={amountDueNow}
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
            estimado={precioPorNoche && phase !== 'payment'}
            sellos={empresa ? [empresa] : undefined}
            destinoTarjeta={destinoTarjetaPago}
            ayudaMensaje={ayudaMensaje}
            onSubmit={iniciarPago}
            onCaptchaToken={(token) => (captchaToken.current = token)}
          />
        }
      />

      <AyudaFlotante
        visible={ayuda.visible}
        etiqueta={dict.feedback.floatingHelp.label}
        cerrarLabel={dict.feedback.floatingHelp.dismiss}
        mensaje={ayuda.motivo === 'tope-personas'
          ? dict.feedback.floatingHelp.messageMaxPeople
              .replace('{name}', servicio?.nombre ?? servicioNombre ?? '')
              .replace('{max}', String(topePersonas))
          : dict.feedback.floatingHelp.messageValidation
              .replace('{date}', diaTexto)
              .replace('{people}', String(people))}
        onDescartar={ayuda.descartar}
      />
    </>
    </ProveedorCambioPrecio>
  );
}
