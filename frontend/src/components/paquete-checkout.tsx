'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Buildings, EnvelopeSimple, MapPin, Phone, User } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { DateField } from '@/components/date-field';
import { CLASES_CAMPO_CON_ERROR, FieldError, propsDeError } from '@/components/field-error';
import { FieldPopover } from '@/components/field-popover';
import { PeopleStepper } from '@/components/people-stepper';
import { SiteHeader } from '@/components/site-header';
import { StripePanel } from '@/components/stripe-panel';
import { TimeField } from '@/components/time-field';
import {
  ApiError,
  confirmarCapturaOrden,
  crearOrden,
  crearPagoOrden,
  getOrden,
  type CrearOrdenInput,
  type OrdenDetalle,
  type PagoOrdenItem,
  type PaqueteCatalogo,
  type TipoTraslado,
  type TrasladosCatalogo,
  type Zona,
} from '@/lib/api';
import { fromLocalISODate, getMinBookableDate, toLocalISODate, TOUR_HOURS } from '@/lib/dates';
import { mensajeDeFallo } from '@/lib/errores';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { leerRef } from '@/lib/ref';

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

type ComponenteEstado = {
  servicioSlug: string;
  nombre: string;
  esTransporte: boolean;
  fecha: string;
  hora: string;
  personas: number;
  tipoTraslado: TipoTraslado;
  modoHospedaje: 'catalogo' | 'personalizada';
  puntoEncuentroId: number | null;
  direccionPersonalizada: string;
  zonaPersonalizada: Zona | '';
  fechaRegreso: string | null;
};

function zonaEfectivaDe(comp: ComponenteEstado, catalogo: TrasladosCatalogo | null): Zona | '' {
  if (comp.tipoTraslado !== 'redondo_actividad') return '';
  if (comp.modoHospedaje === 'catalogo' && comp.puntoEncuentroId !== null) {
    const punto = catalogo?.puntos_encuentro.find((p) => p.id === comp.puntoEncuentroId);
    return punto?.zona ?? '';
  }
  return comp.zonaPersonalizada;
}

type Phase = 'resuming' | 'form' | 'submitting' | 'paying' | 'capturing' | 'success' | 'fail';

type PaqueteCheckoutProps = {
  lang: Locale;
  dict: Dictionary;
  paquete: PaqueteCatalogo;
  sedeSlug: string;
  trasladoCatalogo: TrasladosCatalogo | null;
};

export function PaqueteCheckout({ lang, dict, paquete, sedeSlug, trasladoCatalogo }: PaqueteCheckoutProps) {
  const { checkout, traslados, feedback, nav, footer, booking, paqueteCheckout: pc } = dict;

  const claveStorage = `salysol:orden:${paquete.slug}`;
  const minDate = useMemo(() => getMinBookableDate(), []);

  const [checkoutId, setCheckoutId] = useState('');
  const [ordenId, setOrdenId] = useState<number | null>(null);
  const [phase, setPhase] = useState<Phase>('resuming');

  /* eslint-disable react-hooks/set-state-in-effect -- lectura unica de sessionStorage en cliente */
  useLayoutEffect(() => {
    let guardado: { checkoutId?: string; ordenId?: number } | null = null;
    try {
      const crudo = window.sessionStorage.getItem(claveStorage);
      guardado = crudo ? JSON.parse(crudo) : null;
    } catch {
      guardado = null;
    }

    if (guardado?.checkoutId) {
      setCheckoutId(guardado.checkoutId);
      if (guardado.ordenId) {
        setOrdenId(guardado.ordenId);
        return;
      }
    } else {
      const nuevo = crypto.randomUUID();
      try {
        window.sessionStorage.setItem(claveStorage, JSON.stringify({ checkoutId: nuevo }));
      } catch {
        // Modo privado o almacenamiento lleno: el checkout sigue funcionando,
        // solo no sobrevive a un recargue.
      }
      setCheckoutId(nuevo);
    }
    setPhase('form');
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al montar
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const [componentes, setComponentes] = useState<Record<string, ComponenteEstado>>(() => {
    const inicial: Record<string, ComponenteEstado> = {};
    for (const item of paquete.servicios_asociados) {
      const esTransporte = item.servicio.tipo_servicio === 'transporte';
      inicial[item.servicio.slug] = {
        servicioSlug: item.servicio.slug,
        nombre: item.servicio.nombre,
        esTransporte,
        fecha: minDate,
        hora: '07:00',
        personas: 2,
        tipoTraslado: 'redondo_actividad',
        modoHospedaje: 'catalogo',
        puntoEncuentroId: trasladoCatalogo?.puntos_encuentro[0]?.id ?? null,
        direccionPersonalizada: '',
        zonaPersonalizada: '',
        fechaRegreso: diaSiguiente(minDate),
      };
    }
    return inicial;
  });

  const actualizarComponente = (slug: string, cambios: Partial<ComponenteEstado>) => {
    setComponentes((prev) => ({ ...prev, [slug]: { ...prev[slug], ...cambios } }));
  };

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

  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [errorWaiver, setErrorWaiver] = useState(false);
  const [errorForm, setErrorForm] = useState('');

  const [pagos, setPagos] = useState<PagoOrdenItem[]>([]);
  const [pagoIndex, setPagoIndex] = useState(0);
  const [failMotivo, setFailMotivo] = useState('');

  // Reanudacion: hay ordenId guardado (recargue o reapertura). Consulta el
  // estado real de la orden y retoma exactamente donde se quedo — no repite
  // pasos ya autorizados (ver docs/superpowers/plans, SP2 Seccion 8, punto 5).
  useEffect(() => {
    if (phase !== 'resuming' && ordenId === null) return;
    if (ordenId === null) return;

    let cancelado = false;

    getOrden(sedeSlug, ordenId)
      .then((detalle: OrdenDetalle) => {
        if (cancelado) return;
        if (detalle.estado === 'capturada') {
          setPhase('success');
          return;
        }
        if (detalle.estado === 'cancelada') {
          setPhase('fail');
          return;
        }
        if (detalle.estado === 'autorizando' || detalle.estado === 'autorizada') {
          const pagosResumidos: PagoOrdenItem[] = detalle.reservas.map((r) => ({
            empresa_slug: r.empresa_slug,
            monto: r.pago.monto ?? '0',
            client_secret: r.pago.client_secret ?? '',
            publishable_key: r.pago.publishable_key,
          }));
          setPagos(pagosResumidos);
          const primerPendiente = detalle.reservas.findIndex(
            (r) => !['requires_capture', 'succeeded'].includes(r.pago.estado_pi ?? ''),
          );
          if (primerPendiente === -1) {
            setPhase('capturing');
          } else {
            setPagoIndex(primerPendiente);
            setPhase('paying');
          }
          return;
        }
        // 'armando': la orden se creo pero nunca se llego a crear-pago. Vuelve
        // al formulario reutilizando el mismo checkout_id/orden_id (idempotente).
        setPhase('form');
      })
      .catch(() => {
        if (cancelado) return;
        try {
          window.sessionStorage.removeItem(claveStorage);
        } catch {
          // sin almacenamiento disponible, no hay nada que limpiar
        }
        setOrdenId(null);
        setPhase('form');
      });

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo cuando cambia ordenId
  }, [ordenId]);

  // Dispara la captura final en cuanto todos los pasos quedan autorizados
  // (tanto al terminar la secuencia normal como al reanudar con todo listo).
  useEffect(() => {
    if (phase !== 'capturing' || ordenId === null) return;
    let cancelado = false;
    let timer: ReturnType<typeof setTimeout>;
    const aplicarEstado = (resultado: { estado: string; motivo?: string }) => {
      if (cancelado) return true;
      if (resultado.estado === 'capturada') {
        setPhase('success');
        return true;
      }
      if (resultado.estado === 'cancelada') {
        setFailMotivo(resultado.motivo ?? '');
        setPhase('fail');
        return true;
      }
      return false;
    };
    const consultar = async () => {
      try {
        if (aplicarEstado(await getOrden(sedeSlug, ordenId))) return;
      } catch {
        // Una respuesta perdida no prueba que el cobro falló. Conservar la orden.
      }
      if (!cancelado) timer = setTimeout(consultar, 5000);
    };
    confirmarCapturaOrden(sedeSlug, ordenId)
      .then((resultado) => {
        if (!aplicarEstado(resultado)) timer = setTimeout(consultar, 5000);
      })
      .catch(() => {
        if (!cancelado) timer = setTimeout(consultar, 5000);
      });

    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [phase, ordenId, sedeSlug]);

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

  const validarComponentes = (): string => {
    for (const comp of Object.values(componentes)) {
      if (!comp.fecha) return traslados.errors.seleccionaFecha;
      if (!comp.hora) return traslados.errors.seleccionaHora;
      if (comp.esTransporte) {
        if (comp.modoHospedaje === 'catalogo' && comp.puntoEncuentroId === null) {
          return traslados.errors.seleccionaHospedaje;
        }
        if (comp.modoHospedaje === 'personalizada' && !comp.direccionPersonalizada.trim()) {
          return traslados.errors.seleccionaHospedaje;
        }
        if (comp.tipoTraslado === 'redondo_actividad' && !zonaEfectivaDe(comp, trasladoCatalogo)) {
          return traslados.errors.seleccionaZona;
        }
        if (comp.tipoTraslado === 'redondo_aeropuerto' && !comp.fechaRegreso) {
          return traslados.errors.seleccionaFechaRegreso;
        }
      }
    }
    return '';
  };

  const crearYPagar = async () => {
    const errsContacto = validarContacto();
    setErroresContacto(errsContacto);
    if (Object.keys(errsContacto).length > 0) {
      const primero = ORDEN_CAMPOS.find((c) => errsContacto[c]);
      if (primero) refsContacto[primero].current?.focus();
      return;
    }
    if (!waiverAccepted) {
      setErrorWaiver(true);
      return;
    }
    const msgComponentes = validarComponentes();
    if (msgComponentes) {
      setErrorForm(msgComponentes);
      return;
    }
    if (phase === 'submitting' || phase === 'paying' || phase === 'capturing') return;

    setPhase('submitting');
    setErrorForm('');

    try {
      const payload: CrearOrdenInput = {
        checkout_id: checkoutId,
        paquete: paquete.slug,
        deslinde_aceptado: waiverAccepted,
        deslinde_nombre: contact.fullName.trim(),
        nombre_cliente: contact.fullName.trim(),
        telefono_cliente: contact.phone.trim(),
        correo_cliente: contact.email.trim(),
        ref: leerRef(),
        componentes: Object.values(componentes).map((comp) => ({
          servicio: comp.servicioSlug,
          fecha: comp.fecha,
          hora: comp.hora,
          numero_personas: comp.personas,
          ...(comp.esTransporte
            ? {
                tipo_traslado: comp.tipoTraslado,
                punto_encuentro: comp.modoHospedaje === 'catalogo' ? comp.puntoEncuentroId : undefined,
                direccion_personalizada:
                  comp.modoHospedaje === 'personalizada' ? comp.direccionPersonalizada.trim() : undefined,
                zona: zonaEfectivaDe(comp, trasladoCatalogo),
                fecha_regreso: comp.tipoTraslado === 'redondo_aeropuerto' ? comp.fechaRegreso : null,
              }
            : {}),
        })),
      };

      const creada = await crearOrden(sedeSlug, payload);
      setOrdenId(creada.orden_id);
      try {
        window.sessionStorage.setItem(claveStorage, JSON.stringify({ checkoutId, ordenId: creada.orden_id }));
      } catch {
        // sin almacenamiento disponible: si recarga, empieza de cero
      }

      const pagosResp = await crearPagoOrden(sedeSlug, creada.orden_id);
      setPagos(pagosResp);
      setPagoIndex(0);
      setPhase('paying');
    } catch (err) {
      setErrorForm(
        err instanceof ApiError && err.status === 502
          ? pc.errorPaymentProvider
          : mensajeDeFallo(err, feedback.error) || pc.errorGeneric,
      );
      setPhase('form');
    }
  };

  const onPagoConfirmado = () => {
    setPagoIndex((i) => {
      const esUltimo = i >= pagos.length - 1;
      if (esUltimo) {
        setPhase('capturing');
        return i;
      }
      return i + 1;
    });
  };

  const ayudaMensaje = `Paquete: ${paquete.nombre}. Cliente: ${contact.fullName || '(sin nombre)'}.`;

  if (phase === 'success') {
    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{pc.success.title}</h1>
          <p className="text-sm text-muted">
            {pc.success.body.replace('{total}', String(paquete.servicios_asociados.length))}
          </p>
          <div className="w-full rounded-xl border border-border bg-card p-5 text-left">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
              {pc.success.componentsHeadline}
            </p>
            <ul className="flex flex-col gap-2">
              {paquete.servicios_asociados.map((item) => (
                <li key={item.id} className="text-sm text-foreground">
                  {item.servicio.nombre}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <CheckoutFooter lang={lang} footer={footer} nav={nav} />
      </div>
    );
  }

  if (phase === 'fail') {
    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{pc.fail.title}</h1>
          <p className="text-sm text-muted">{pc.fail.body}</p>
          {failMotivo && (
            <p className="text-xs text-muted">
              {pc.fail.motivoPrefix}
              {failMotivo}
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              try {
                window.sessionStorage.removeItem(claveStorage);
              } catch {
                // nada que limpiar
              }
              window.location.reload();
            }}
            className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground"
          >
            {pc.fail.retry}
          </button>
        </div>
        <CheckoutFooter lang={lang} footer={footer} nav={nav} />
      </div>
    );
  }

  const nombrePorEmpresa = new Map(
    paquete.servicios_asociados.map((item) => [item.servicio.empresa_slug, item.servicio.nombre]),
  );
  const pagoActual = pagos[pagoIndex];
  const labelPagoActual = pagoActual ? (nombrePorEmpresa.get(pagoActual.empresa_slug) ?? pagoActual.empresa_slug) : '';
  const montoPagoActual = pagoActual ? formatearPrecio(parseFloat(pagoActual.monto), 'MXN') : '';

  if (phase === 'resuming') {
    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <div className="mx-auto max-w-2xl px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
          <p className="text-sm text-muted">{pc.resumingNotice}</p>
        </div>
      </div>
    );
  }

  if (phase === 'capturing') {
    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <div className="mx-auto max-w-2xl px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
          <p className="text-sm text-muted">{checkout.submitting}</p>
          <p className="mt-3 text-sm text-muted">{feedback.paySlow}</p>
        </div>
      </div>
    );
  }

  if (phase === 'paying' && pagoActual) {
    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />
        <div className="mx-auto max-w-xl px-6 pt-[calc(2rem_+_var(--nav-alto))] pb-20 sm:px-8">
          <p className="mb-4 text-center text-sm font-medium text-foreground">
            {pc.stepOf
              .replace('{n}', String(pagoIndex + 1))
              .replace('{total}', String(pagos.length))
              .replace('{label}', labelPagoActual)
              .replace('{amount}', montoPagoActual)}
          </p>
          <StripePanel
            key={pagoActual.empresa_slug}
            lang={lang}
            checkout={checkout}
            waiverAccepted={true}
            onWaiverChange={() => {}}
            errorWaiver={false}
            lines={[{ label: labelPagoActual, amount: montoPagoActual }]}
            total={montoPagoActual}
            amountDueNow={montoPagoActual}
            moneda="MXN"
            onMonedaChange={() => {}}
            usdDisponible={false}
            formaPago="completo"
            onFormaPagoChange={() => {}}
            codigoPromocional=""
            onCodigoPromocionalChange={() => {}}
            promoEstado="idle"
            promoPorcentaje={null}
            phase="payment"
            error=""
            pago={{
              client_secret: pagoActual.client_secret,
              publishable_key: pagoActual.publishable_key,
              monto_a_cobrar: pagoActual.monto,
              moneda: 'MXN',
            }}
            feedback={feedback}
            ayudaMensaje={ayudaMensaje}
            onSubmit={() => {}}
            onPagoConfirmado={onPagoConfirmado}
            onPagoRechazado={(mensaje) => {
              setFailMotivo(mensaje);
              setPhase('capturing');
            }}
            onCaptchaToken={() => {}}
          />
        </div>
        <CheckoutFooter lang={lang} footer={footer} nav={nav} />
      </div>
    );
  }

  // FORM: un solo formulario con los datos de contacto, cada componente del
  // paquete, y un deslinde unico que ampara a todas las empresas (ver plan
  // SP2 Seccion 9, "un solo deslinde ampara a todas las empresas").
  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />

      <div className="mx-auto max-w-3xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] pb-24 sm:px-8">
        <Link
          href={`/${lang}/sede/${sedeSlug}`}
          className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {pc.back}
        </Link>

        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{pc.headline}</h1>
        <p className="mt-2 text-sm text-muted">
          {pc.subtitle.replace('{total}', String(paquete.servicios_asociados.length))}
        </p>

        <div className="mt-8 flex flex-col gap-6">
          <CheckoutSectionCard title={pc.contactTitle} variant="flat">
            <div className="flex flex-col gap-4">
              <label className="flex flex-col gap-1.5 text-sm">
                <span className="text-muted">{checkout.fullName}</span>
                <div className="relative">
                  <User size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                  <input
                    ref={refFullName}
                    type="text"
                    value={contact.fullName}
                    onChange={(e) => setContact((c) => ({ ...c, fullName: e.target.value }))}
                    {...propsDeError('error-fullName', Boolean(erroresContacto.fullName))}
                    className={`w-full border py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent ${
                      erroresContacto.fullName ? CLASES_CAMPO_CON_ERROR : 'border-border bg-surface'
                    }`}
                  />
                </div>
                {erroresContacto.fullName && <FieldError id="error-fullName" mensaje={erroresContacto.fullName} />}
              </label>

              <label className="flex flex-col gap-1.5 text-sm">
                <span className="text-muted">{checkout.phone}</span>
                <div className="relative">
                  <Phone size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                  <input
                    ref={refPhone}
                    type="tel"
                    value={contact.phone}
                    onChange={(e) => setContact((c) => ({ ...c, phone: e.target.value }))}
                    {...propsDeError('error-phone', Boolean(erroresContacto.phone))}
                    className={`w-full border py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent ${
                      erroresContacto.phone ? CLASES_CAMPO_CON_ERROR : 'border-border bg-surface'
                    }`}
                  />
                </div>
                {erroresContacto.phone && <FieldError id="error-phone" mensaje={erroresContacto.phone} />}
              </label>

              <label className="flex flex-col gap-1.5 text-sm">
                <span className="text-muted">{checkout.email}</span>
                <div className="relative">
                  <EnvelopeSimple
                    size={18}
                    className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
                  />
                  <input
                    ref={refEmail}
                    type="email"
                    value={contact.email}
                    onChange={(e) => setContact((c) => ({ ...c, email: e.target.value }))}
                    {...propsDeError('error-email', Boolean(erroresContacto.email))}
                    className={`w-full border py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent ${
                      erroresContacto.email ? CLASES_CAMPO_CON_ERROR : 'border-border bg-surface'
                    }`}
                  />
                </div>
                {erroresContacto.email && <FieldError id="error-email" mensaje={erroresContacto.email} />}
              </label>
            </div>
          </CheckoutSectionCard>

          {Object.values(componentes).map((comp) => (
            <CheckoutSectionCard
              key={comp.servicioSlug}
              title={`${comp.esTransporte ? pc.componentTrasladoTitle : pc.componentPescaTitle} — ${comp.nombre}`}
              variant="flat"
            >
              {comp.esTransporte ? (
                <div className="flex flex-col gap-4">
                  <fieldset className="grid gap-3 sm:grid-cols-3">
                    <legend className="sr-only">{traslados.step1Title}</legend>
                    {(['redondo_aeropuerto', 'redondo_actividad', 'recepcion_aeropuerto'] as const).map((tipo) => (
                      <label
                        key={tipo}
                        className={`cursor-pointer rounded-lg border p-3 text-sm transition-colors ${
                          comp.tipoTraslado === tipo
                            ? 'border-accent bg-surface font-medium text-foreground ring-1 ring-accent'
                            : 'border-border text-muted hover:border-border-strong'
                        }`}
                      >
                        <input
                          type="radio"
                          name={`tipo-traslado-${comp.servicioSlug}`}
                          checked={comp.tipoTraslado === tipo}
                          onChange={() => actualizarComponente(comp.servicioSlug, { tipoTraslado: tipo })}
                          className="sr-only"
                        />
                        {traslados.types[tipo]?.title ?? tipo}
                      </label>
                    ))}
                  </fieldset>

                  {trasladoCatalogo && (
                    <FieldPopover
                      label={traslados.fields.puntoEncuentro}
                      value={
                        comp.modoHospedaje === 'catalogo'
                          ? (trasladoCatalogo.puntos_encuentro.find((p) => p.id === comp.puntoEncuentroId)?.nombre ?? '')
                          : ''
                      }
                      vacio={comp.modoHospedaje === 'catalogo' && comp.puntoEncuentroId === null}
                      placeholder={traslados.fields.puntoEncuentroPlaceholder}
                      icon={<Buildings size={20} className="shrink-0 text-muted" />}
                    >
                      {(cerrar) => (
                        <div className="max-h-72 w-full overflow-y-auto sm:w-80">
                          <ul className="flex flex-col gap-1">
                            {trasladoCatalogo.puntos_encuentro.map((p) => (
                              <li key={p.id}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    actualizarComponente(comp.servicioSlug, {
                                      modoHospedaje: 'catalogo',
                                      puntoEncuentroId: p.id,
                                    });
                                    cerrar();
                                  }}
                                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                                    p.id === comp.puntoEncuentroId
                                      ? 'bg-accent font-medium text-accent-foreground'
                                      : 'text-foreground hover:bg-background'
                                  }`}
                                >
                                  <span className="truncate pr-2">{p.nombre}</span>
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </FieldPopover>
                  )}

                  {comp.modoHospedaje === 'personalizada' && (
                    <div className="flex flex-col gap-3">
                      <label className="flex flex-col gap-1.5 text-sm">
                        <span className="text-muted">{traslados.fields.otraDireccion}</span>
                        <div className="relative">
                          <MapPin size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                          <input
                            type="text"
                            value={comp.direccionPersonalizada}
                            onChange={(e) =>
                              actualizarComponente(comp.servicioSlug, { direccionPersonalizada: e.target.value })
                            }
                            placeholder={traslados.fields.direccionPlaceholder}
                            className="w-full border border-border bg-surface py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent"
                          />
                        </div>
                      </label>
                      {comp.tipoTraslado === 'redondo_actividad' && (
                        <div className="grid grid-cols-2 gap-3">
                          {(['centro', 'periferia'] as const).map((z) => (
                            <label
                              key={z}
                              className={`flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm ${
                                comp.zonaPersonalizada === z ? 'border-accent bg-surface font-medium' : 'border-border text-muted'
                              }`}
                            >
                              <input
                                type="radio"
                                name={`zona-${comp.servicioSlug}`}
                                checked={comp.zonaPersonalizada === z}
                                onChange={() => actualizarComponente(comp.servicioSlug, { zonaPersonalizada: z })}
                                className="h-4 w-4 accent-accent"
                              />
                              {z === 'centro' ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() =>
                      actualizarComponente(comp.servicioSlug, {
                        modoHospedaje: comp.modoHospedaje === 'catalogo' ? 'personalizada' : 'catalogo',
                      })
                    }
                    className="self-start text-xs font-medium text-accent underline underline-offset-2"
                  >
                    {comp.modoHospedaje === 'catalogo' ? traslados.fields.otraDireccion : traslados.fields.puntoEncuentro}
                  </button>

                  <div className="grid gap-3 border-t border-border pt-4 sm:grid-cols-2">
                    <DateField
                      lang={lang}
                      label={traslados.fields.fecha}
                      value={comp.fecha}
                      onChange={(f) => {
                        actualizarComponente(comp.servicioSlug, { fecha: f });
                        if (comp.fechaRegreso && comp.fechaRegreso <= f) {
                          actualizarComponente(comp.servicioSlug, { fechaRegreso: diaSiguiente(f) });
                        }
                      }}
                      minDate={minDate}
                      prevMonthLabel={booking.prevMonth}
                      nextMonthLabel={booking.nextMonth}
                      personas={comp.personas}
                      fullLabel={checkout.dayFull}
                      sinCupo={true}
                    />
                    <TimeField
                      label={traslados.fields.hora}
                      help={checkout.hourLabel}
                      value={comp.hora}
                      onChange={(h) => actualizarComponente(comp.servicioSlug, { hora: h })}
                      availableHours={TOUR_HOURS}
                    />
                  </div>

                  {comp.tipoTraslado === 'redondo_aeropuerto' && (
                    <DateField
                      lang={lang}
                      label={traslados.fields.fechaRegreso}
                      value={comp.fechaRegreso}
                      onChange={(f) => actualizarComponente(comp.servicioSlug, { fechaRegreso: f })}
                      minDate={diaSiguiente(comp.fecha)}
                      prevMonthLabel={booking.prevMonth}
                      nextMonthLabel={booking.nextMonth}
                      personas={comp.personas}
                      fullLabel={checkout.dayFull}
                      sinCupo={true}
                    />
                  )}
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  <DateField
                    lang={lang}
                    label={checkout.dayLabel}
                    value={comp.fecha}
                    onChange={(f) => actualizarComponente(comp.servicioSlug, { fecha: f })}
                    minDate={minDate}
                    prevMonthLabel={booking.prevMonth}
                    nextMonthLabel={booking.nextMonth}
                    personas={comp.personas}
                    fullLabel={checkout.dayFull}
                    sinCupo={true}
                  />
                  <TimeField
                    label={checkout.hourLabel}
                    help={checkout.hourLabel}
                    value={comp.hora}
                    onChange={(h) => actualizarComponente(comp.servicioSlug, { hora: h })}
                  />
                </div>
              )}

              <div className="mt-4 border-t border-border pt-4">
                <PeopleStepper
                  label={checkout.peopleLabel}
                  maxNotice={traslados.fields.maxPasajerosNotice.replace('{max}', '5')}
                  value={comp.personas}
                  onChange={(v) => actualizarComponente(comp.servicioSlug, { personas: v })}
                />
              </div>
            </CheckoutSectionCard>
          ))}

          {errorForm && <FieldError id="error-form" mensaje={errorForm} />}

          <CheckoutSectionCard title={checkout.orderSummaryHeadline} variant="elevated">
            <label className="flex items-start gap-2.5 pb-5 text-xs leading-relaxed text-muted">
              <input
                type="checkbox"
                checked={waiverAccepted}
                disabled={phase === 'submitting'}
                onChange={(e) => {
                  setWaiverAccepted(e.target.checked);
                  if (e.target.checked) setErrorWaiver(false);
                }}
                {...propsDeError('error-waiver', errorWaiver)}
                className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-accent"
              />
              <span>
                {checkout.waiver.accept}{' '}
                <Link href={`/${lang}/deslinde`} target="_blank" rel="noopener" className="text-foreground underline underline-offset-2">
                  {checkout.waiver.linkLabel}
                </Link>{' '}
                {checkout.waiver.and}{' '}
                <Link href={`/${lang}/privacidad`} target="_blank" rel="noopener" className="text-foreground underline underline-offset-2">
                  {checkout.waiver.privacyLinkLabel}
                </Link>
                .
              </span>
            </label>
            {errorWaiver && <FieldError id="error-waiver" mensaje={checkout.waiver.missing} />}

            <button
              type="button"
              onClick={crearYPagar}
              disabled={phase === 'submitting'}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-action px-4 py-3 text-sm font-medium text-action-foreground transition-opacity disabled:opacity-60"
            >
              {phase === 'submitting' ? pc.submitting : pc.submit}
            </button>
          </CheckoutSectionCard>
        </div>
      </div>

      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );
}
