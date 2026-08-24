'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Warning } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { AmenitiesReminder } from '@/components/amenities-reminder';
import { BookingConfirmation } from '@/components/booking-confirmation';
import { SiteHeader } from '@/components/site-header';
import { CheckoutCalendar } from '@/components/checkout-calendar';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { CLASES_CAMPO_CON_ERROR, FieldError, propsDeError } from '@/components/field-error';
import { PeopleStepper } from '@/components/people-stepper';
import { StripePanel } from '@/components/stripe-panel';
import { TimeField } from '@/components/time-field';
import { Turnstile } from '@/components/turnstile';
import { useToast } from '@/components/toast';
import {
  ApiError,
  crearPago,
  getCupo,
  guardarReserva,
  type Moneda,
  type Pago,
  type SolicitudKey,
  type Tarifa,
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

// Bebidas y transporte no tienen precio en linea: su costo depende del tipo de
// bebida y de la distancia del traslado, asi que el agente los cotiza aparte.
const SOLICITUD_KEYS: SolicitudKey[] = ['drinks', 'transport'];

const CLAVE_CHECKOUT_ID = 'salysol:checkout-id';

/**
 * Identificador de esta sesion de checkout. Vive en sessionStorage para que
 * sobreviva a una recarga: el backend lo usa como llave y reescribe la misma
 * reserva en vez de dejar una fila nueva por cada intento.
 */
function useCheckoutId() {
  const [id] = useState(() => {
    if (typeof window === 'undefined') return '';
    const guardado = window.sessionStorage.getItem(CLAVE_CHECKOUT_ID);
    if (guardado) return guardado;
    const nuevo = crypto.randomUUID();
    window.sessionStorage.setItem(CLAVE_CHECKOUT_ID, nuevo);
    return nuevo;
  });
  return id;
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
};

type Phase = 'form' | 'submitting' | 'payment' | 'confirmed' | 'unavailable' | 'error';

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
}: CheckoutViewProps) {
  const { checkout, booking, nav } = dict;
  const checkoutId = useCheckoutId();

  const [day, setDay] = useState(initialDay);
  const [time, setTime] = useState(initialTime);
  const [people, setPeople] = useState(initialPeople);
  const [moneda, setMoneda] = useState<Moneda>('MXN');
  const [lunch, setLunch] = useState(false);
  const [solicitudes, setSolicitudes] = useState({ drinks: false, transport: false });
  const [formaPago, setFormaPago] = useState<'completo' | 'anticipo'>('completo');
  const { mostrar: avisar } = useToast();

  const [contact, setContact] = useState({ phone: '', fullName: '', email: '' });

  // Para poder mandarle el foco al primer campo con error.
  const refPhone = useRef<HTMLInputElement>(null);
  const refFullName = useRef<HTMLInputElement>(null);
  const refEmail = useRef<HTMLInputElement>(null);
  const refsContacto: Record<CampoContacto, React.RefObject<HTMLInputElement | null>> = {
    phone: refPhone,
    fullName: refFullName,
    email: refEmail,
  };
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [phase, setPhase] = useState<Phase>(tarifa ? 'form' : 'unavailable');
  const [error, setError] = useState('');
  const [pago, setPago] = useState<Pago | null>(null);
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

  // Solo se ofrecen dolares si el negocio fijo un precio en dolares.
  const usdDisponible = tarifa?.precio_usd != null;
  const tourPrice = tarifa ? Number(moneda === 'MXN' ? tarifa.precio : tarifa.precio_usd) : null;
  const precioLunch = tarifa
    ? Number(moneda === 'MXN' ? tarifa.precio_lunch : tarifa.precio_lunch_usd)
    : 0;

  const currency = useMemo(
    () => new Intl.NumberFormat(intlLocale(lang), { style: 'currency', currency: moneda }),
    [lang, moneda]
  );

  // Lo que se le puede ofrecer todavia al cliente antes de pagar.
  const faltantes = {
    lunch: !lunch,
    solicitudes: SOLICITUD_KEYS.filter((key) => !solicitudes[key]),
  };
  const hayAlgoQueOfrecer = faltantes.lunch || faltantes.solicitudes.length > 0;

  // El precio es por viaje (la reserva es de la embarcacion completa), pero
  // pasando de las personas incluidas se suma un cargo por cada una. El servidor
  // recalcula esto mismo al crear el pago: aqui solo se muestra.
  const personasIncluidas = tarifa?.personas_incluidas ?? 0;
  const precioPersonaExtra = tarifa
    ? Number(moneda === 'MXN' ? tarifa.precio_persona_extra : tarifa.precio_persona_extra_usd)
    : 0;
  const personasExtra = Math.max(0, people - personasIncluidas);
  const cargoPersonas = personasExtra * (precioPersonaExtra || 0);

  // Un lunch por persona: comen todos los que van a bordo.
  const cargoLunch = lunch ? precioLunch * people : 0;

  const lines =
    tourPrice === null
      ? []
      : [
          { label: checkout.tourLabel, amount: currency.format(tourPrice) },
          ...(cargoPersonas > 0
            ? [{
                label: `${checkout.extraPeopleLabel} (${personasExtra} × ${currency.format(precioPersonaExtra)})`,
                amount: currency.format(cargoPersonas),
              }]
            : []),
          ...(cargoLunch > 0
            ? [{
                label: `Lunch (${people} × ${currency.format(precioLunch)})`,
                amount: currency.format(cargoLunch),
              }]
            : []),
        ];

  const total = tourPrice === null ? null : tourPrice + cargoPersonas + cargoLunch;
  const amountDueNow =
    total === null ? null : formaPago === 'completo' ? total : Math.round(total * 0.3 * 100) / 100;

  const dayDate = useMemo(() => fromLocalISODate(day), [day]);

  /** Que campo esta mal y por que. Vacio = ninguno. */
  const [erroresCampo, setErroresCampo] = useState<Partial<Record<CampoContacto, string>>>({});

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

    if (hayAlgoQueOfrecer) {
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
        // Los extras viajan con la reserva, no con el pago: la cocina necesita
        // saber cuantos lunches y la vendedora a quien cotizarle.
        lleva_lunch: lunch,
        pide_bebidas: solicitudes.drinks,
        pide_transporte: solicitudes.transport,
        // A quien le cuenta la venta, si el cliente llego por el link de alguien.
        ref: leerRef(),
        captcha_token: captchaToken.current,
      });

      const pagoResponse = await crearPago(reserva.id, {
        checkout_id: checkoutId,
        forma_pago: formaPago,
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
      setError(mensajeDeError(err, checkout, dict.feedback));
      setPhase('error');
    }
  };

  const locked = phase === 'payment' || phase === 'unavailable';
  // Token de Turnstile. Lo produce el widget solo; el backend lo exige unicamente
  // al crear la reserva, asi que estar vacio no bloquea un reenvio.
  const captchaToken = useRef('');

  const enviando = phase === 'submitting';

  // Lo que se le manda a la vendedora si el cliente usa la salida de emergencia
  // de un error. Lleva su fecha, hora y grupo para que ella no tenga que
  // preguntarlos y el no tenga que redactar nada ya estando frustrado.
  const ayudaMensaje = mensajeDeAyuda(dict.feedback.helpMessage, {
    fecha: formatDay(dayDate, lang),
    hora: formatHour(time),
    personas: people,
  });

  if (phase === 'confirmed') {
    const porCotizar = SOLICITUD_KEYS.filter((key) => solicitudes[key]).map(
      (key) => checkout.amenities[key]
    );

    return (
      <BookingConfirmation
        lang={lang}
        dict={dict}
        email={contact.email}
        fecha={formatDay(dayDate, lang)}
        hora={formatHour(time)}
        personas={people}
        pagado={amountDueNow === null ? '—' : currency.format(amountDueNow)}
        saldoEnEfectivo={
          total !== null && amountDueNow !== null && total > amountDueNow
            ? currency.format(total - amountDueNow)
            : null
        }
        porCotizar={porCotizar}
        procesando={pagoProcesando}
      />
    );
  }

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={nav} tone="plain" />

      <div className="mx-auto max-w-6xl px-6 pt-6 sm:px-8 lg:px-12">
        <Link
          href={`/${lang}`}
          className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {checkout.back}
        </Link>
      </div>

      {sinLugar && (
        <div className="mx-auto mb-2 flex max-w-6xl items-start gap-3 px-6 sm:px-8 lg:px-12">
          <div className="flex w-full flex-col gap-2 rounded-2xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-foreground sm:flex-row sm:items-center sm:justify-between">
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

      {/* 3fr/2fr: los pasos necesitan el ancho (calendario, formulario), el
          resumen es una columna de cifras y se lee mejor angosta. */}
      <main className="mx-auto grid max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex flex-col gap-6">
          <CheckoutSectionCard step={1} title={checkout.tripHeadline}>
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
          </CheckoutSectionCard>

          <CheckoutSectionCard step={2} title={checkout.contactHeadline}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-sm sm:col-span-1">
                <span className="text-muted">{checkout.phone}</span>
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
                    if (erroresCampo.phone) setErroresCampo((prev) => ({ ...prev, phone: undefined }));
                  }}
                  {...propsDeError('error-phone', Boolean(erroresCampo.phone))}
                  className={`rounded-xl border bg-background px-4 py-3 text-foreground outline-none disabled:opacity-60 ${
                    erroresCampo.phone ? CLASES_CAMPO_CON_ERROR : 'border-border focus:border-accent'
                  }`}
                />
                {erroresCampo.phone && (
                  <FieldError id="error-phone" mensaje={erroresCampo.phone} />
                )}
              </label>
              <label className="flex flex-col gap-1.5 text-sm sm:col-span-1">
                <span className="text-muted">{checkout.fullName}</span>
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
                    if (erroresCampo.fullName) setErroresCampo((prev) => ({ ...prev, fullName: undefined }));
                  }}
                  {...propsDeError('error-fullName', Boolean(erroresCampo.fullName))}
                  className={`rounded-xl border bg-background px-4 py-3 text-foreground outline-none disabled:opacity-60 ${
                    erroresCampo.fullName ? CLASES_CAMPO_CON_ERROR : 'border-border focus:border-accent'
                  }`}
                />
                {erroresCampo.fullName && (
                  <FieldError id="error-fullName" mensaje={erroresCampo.fullName} />
                )}
              </label>
              <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
                <span className="text-muted">{checkout.email}</span>
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
                    if (erroresCampo.email) setErroresCampo((prev) => ({ ...prev, email: undefined }));
                  }}
                  {...propsDeError('error-email', Boolean(erroresCampo.email))}
                  className={`rounded-xl border bg-background px-4 py-3 text-foreground outline-none disabled:opacity-60 ${
                    erroresCampo.email ? CLASES_CAMPO_CON_ERROR : 'border-border focus:border-accent'
                  }`}
                />
                {erroresCampo.email && (
                  <FieldError id="error-email" mensaje={erroresCampo.email} />
                )}
              </label>
            </div>
          </CheckoutSectionCard>

          {/* El punto de encuentro y el aviso del agente ya no van aqui: son
              informacion de despues de pagar, viven en BookingConfirmation. */}
          <CheckoutSectionCard step={3} title={checkout.amenitiesHeadline}>
            <label className="flex items-start justify-between gap-3 rounded-xl border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-background">
              <span className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={lunch}
                  disabled={locked}
                  onChange={(e) => setLunch(e.target.checked)}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                />
                <span>{checkout.amenities.lunch}</span>
              </span>
              <span className="shrink-0 text-right text-muted">
                {currency.format(precioLunch)}
                <span className="block text-xs">{checkout.lunchPerPerson}</span>
              </span>
            </label>

            {/* Bloque aparte y sin precio: que quede claro que esto NO se esta
                pagando ahora, o el cliente llega al muelle creyendo que si. */}
            <div className="mt-8 border-t border-border pt-6">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-medium tracking-tight text-foreground">
                  {checkout.requestsHeadline}
                </h3>
                <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-0.5 text-[11px] text-accent">
                  {checkout.requestsBadge}
                </span>
              </div>
              <p className="mt-2 max-w-[60ch] text-sm leading-relaxed text-muted">
                {checkout.requestsIntro}
              </p>

              <div className="mt-4 flex flex-col gap-3">
                {SOLICITUD_KEYS.map((key) => (
                  <label
                    key={key}
                    className="flex items-start gap-3 rounded-xl border border-dashed border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-solid has-[:checked]:border-accent has-[:checked]:bg-background"
                  >
                    <input
                      type="checkbox"
                      checked={solicitudes[key]}
                      disabled={locked}
                      onChange={(e) =>
                        setSolicitudes((prev) => ({ ...prev, [key]: e.target.checked }))
                      }
                      className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                    />
                    <span>{checkout.amenities[key]}</span>
                  </label>
                ))}
              </div>
            </div>
          </CheckoutSectionCard>
        </div>

        <div className="lg:sticky lg:top-10 lg:self-start">
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
          />
          <Turnstile onToken={(token) => (captchaToken.current = token)} />
        </div>
      </main>

      <CheckoutFooter lang={lang} footer={dict.footer} nav={nav} />

      {recordatorioAbierto && (
        <AmenitiesReminder
          checkout={checkout}
          faltaLunch={faltantes.lunch}
          lunch={lunch}
          onLunchChange={setLunch}
          precioLunch={currency.format(precioLunch)}
          solicitudesFaltantes={faltantes.solicitudes}
          solicitudes={solicitudes}
          onSolicitudChange={(key, valor) =>
            setSolicitudes((prev) => ({ ...prev, [key]: valor }))
          }
          onContinuar={enviar}
          onCerrar={() => setRecordatorioAbierto(false)}
          enviando={enviando}
        />
      )}
    </div>
  );
}
