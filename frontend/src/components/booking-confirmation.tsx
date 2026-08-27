'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import {
  CheckCircle,
  Clock,
  DownloadSimple,
  Fish,
  ForkKnife,
  MapPin,
  Package,
  Question,
  Suitcase,
  UserCheck,
  Van,
  WhatsappLogo,
} from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SiteHeader } from '@/components/site-header';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

type BookingConfirmationProps = {
  lang: Locale;
  dict: Dictionary;
  /** Numero de la reserva. Sirve de folio en pantalla, en el recibo impreso y
   *  en el mensaje de WhatsApp — nada de esto tiene sentido sin algo a lo que
   *  el agente le pueda buscar. */
  numeroDeConfirmacion: number;
  nombre: string;
  email: string;
  fecha: string;
  hora: string;
  personas: number;
  pagado: string;
  /** Lo que queda por pagar en efectivo, o null si pago el 100%. */
  saldoEnEfectivo: string | null;
  /** Stripe puede tardar en acreditar segun el metodo de pago. */
  procesando: boolean;
};

/** Los iconos no van en el diccionario: ahi vive el texto, no el diseño. La
 *  clave `icon` de cada sugerencia es la que los ata. */
const ICONO_SUGERENCIA = {
  equipo: Fish,
  carnada: Package,
  bebidas: ForkKnife,
  traslado: Van,
  especial: Question,
} as const;

/**
 * Pantalla que reemplaza al checkout cuando el pago pasa.
 *
 * Es pantalla completa y no un modal a proposito: ya no hay nada atras a lo que
 * volver, y esto es el comprobante que el cliente va a capturar o enseñar en el
 * muelle. La reserva la marca pagada el webhook de Stripe, no esta vista — aqui
 * solo se le informa al cliente lo que acaba de pasar.
 *
 * Dos columnas en escritorio, y no una sola tira larga, porque son dos cosas
 * distintas: a la izquierda el comprobante (pasivo, se guarda o se imprime) y a
 * la derecha lo que todavia puede hacer (activo, lleva a WhatsApp). Apiladas,
 * las dos competian por el mismo peso visual justo cuando el cliente acaba de
 * gastar toda su atencion en el formulario y el pago.
 *
 * El boton "Descargar recibo" es `window.print()`, no un PDF generado aparte:
 * sin backend nuevo, sin exponer una ruta que busque una reserva ajena por id
 * (justo el hueco que se cerro en `crear-pago`, ver ENDURECIMIENTO.md) y
 * cualquier navegador deja "Guardar como PDF" desde el dialogo de impresion.
 * Las clases `print:` deciden que va en ese papel y que no: solo la columna del
 * comprobante, nunca las sugerencias.
 */
export function BookingConfirmation({
  lang,
  dict,
  numeroDeConfirmacion,
  nombre,
  email,
  fecha,
  hora,
  personas,
  pagado,
  saldoEnEfectivo,
  procesando,
}: BookingConfirmationProps) {
  const { checkout, footer, nav, included } = dict;
  const { confirmation } = checkout;

  // Esta vista no es una pagina nueva: reemplaza al checkout en el mismo montaje,
  // asi que el navegador conserva el scroll donde estaba el formulario de pago y
  // el cliente aterrizaba a media pantalla, sin ver nunca la confirmacion. Salto
  // directo y sin animar: el scroll suave de `globals.css` haria que la primera
  // imagen siga siendo la de en medio.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, []);

  const mensajeWhatsapp = confirmation.whatsappMessage
    .replace('{nombre}', nombre)
    .replace('{fecha}', fecha)
    .replace('{folio}', String(numeroDeConfirmacion));

  /** Cada sugerencia abre WhatsApp con su propia pregunta ya escrita. Un solo
   *  boton generico obliga al cliente a redactar, y lo que no se redacta no se
   *  pregunta: la carnada que no pidio aparece como problema en el muelle. */
  const mensajeDeSugerencia = (ask: string) =>
    confirmation.needsMessage
      .replace('{nombre}', nombre)
      .replace('{fecha}', fecha)
      .replace('{folio}', String(numeroDeConfirmacion))
      .replace('{ask}', ask);

  return (
    <div className="flex min-h-dvh flex-col bg-surface print:bg-white">
      <div className="print:hidden">
        <SiteHeader lang={lang} nav={nav} />
      </div>

      <main className="mx-auto w-full max-w-6xl px-6 py-12 sm:px-8 lg:py-16 print:max-w-none print:p-0">
        {/* El aviso de exito va arriba de las dos columnas y a todo el ancho: es
            lo unico que el cliente necesita ver en el primer cuadro, y compartir
            fila con el detalle del viaje le quitaria ese lugar. */}
        <header className="flex flex-col items-center text-center print:hidden">
          <div className="relative flex items-center justify-center">
            {/* La onda vive detras del icono y no lo mueve: `aria-hidden` porque
                no dice nada que el titular no diga. `motion-safe` no hace falta,
                `prefers-reduced-motion` ya colapsa toda animacion en globals.css. */}
            <span
              aria-hidden
              className="absolute h-16 w-16 rounded-full bg-accent/25 [animation:confirmacion-onda_1.1s_ease-out_2_both]"
            />
            <CheckCircle
              size={68}
              weight="fill"
              className="relative text-accent [animation:confirmacion-pop_0.5s_cubic-bezier(0.16,1,0.3,1)_both]"
            />
          </div>

          <h1 className="mt-6 max-w-[20ch] text-3xl leading-tight text-foreground sm:text-4xl">
            {procesando ? confirmation.processingHeadline : confirmation.headline}
          </h1>

          <p className="mt-4 max-w-[58ch] text-sm leading-relaxed text-muted">
            {procesando
              ? confirmation.processingBody
              : confirmation.emailNotice.replace('{email}', email)}
          </p>
        </header>

        {/* 1.15/0.85: el comprobante lleva cifras y direccion y necesita el ancho;
            las sugerencias son tarjetas cortas y se leen mejor en columna angosta. */}
        <div className="mt-12 grid gap-6 lg:grid-cols-[1.15fr_0.85fr] lg:items-start lg:gap-8 print:mt-0 print:block">
          {/* --- Columna 1: el comprobante. Lo unico que se imprime. --------- */}
          <section className="border border-border bg-background shadow-[0_18px_45px_rgba(11,36,32,0.10)] print:border-0 print:shadow-none">
            {/* Talon del boleto. En pantalla es la cabecera con el folio; en el
                papel hace de membrete, donde no hay SiteHeader que lo diga. */}
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-7 pt-7 sm:px-9 sm:pt-9 print:px-0 print:pt-0">
              <div>
                <p className="text-lg font-semibold text-foreground">
                  {nav.brandMain} {nav.brandAccent}
                </p>
                <p className="mt-0.5 text-xs text-muted">{confirmation.receiptTitle}</p>
              </div>
              <div className="text-right">
                <p className="text-[11px] tracking-wide text-muted">
                  {confirmation.referenceLabel}
                </p>
                <p className="font-sans text-xl font-semibold tracking-tight text-accent print:text-foreground">
                  #{numeroDeConfirmacion}
                </p>
              </div>
            </div>

            {/* Linea de corte, como la de un boleto de verdad. Es decoracion con
                trabajo: separa el talon del detalle sin meter otro titulo. */}
            <div
              aria-hidden
              className="mx-7 mt-6 border-t border-dashed border-border-strong sm:mx-9 print:mx-0"
            />

            <div className="px-7 pb-7 sm:px-9 sm:pb-9 print:px-0 print:pb-0">
              <section className="pt-6">
                <h2 className="font-sans text-sm font-medium tracking-tight text-foreground">
                  {confirmation.tripHeadline}
                </h2>
                <dl className="mt-4 flex flex-col gap-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted">{checkout.dayLabel}</dt>
                    <dd className="text-right text-foreground">{fecha}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted">{checkout.hourLabel}</dt>
                    <dd className="text-right text-foreground">{hora}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted">{checkout.peopleLabel}</dt>
                    <dd className="text-right text-foreground">{personas}</dd>
                  </div>
                  <div className="mt-2 flex justify-between gap-4 border-t border-border pt-3">
                    <dt className="text-muted">{confirmation.paidLabel}</dt>
                    <dd className="text-right font-medium text-foreground">{pagado}</dd>
                  </div>
                  {saldoEnEfectivo && (
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted">{confirmation.pendingLabel}</dt>
                      <dd className="text-right text-foreground">{saldoEnEfectivo}</dd>
                    </div>
                  )}
                </dl>
              </section>

              <section className="mt-7 border-t border-border pt-6">
                <h2 className="flex items-center gap-2 font-sans text-sm font-medium tracking-tight text-foreground">
                  <MapPin size={18} className="shrink-0 text-accent" />
                  {confirmation.meetingHeadline}
                </h2>
                <p className="mt-3 text-sm text-foreground">{footer.address}</p>
                <p className="text-sm text-foreground">{footer.city}</p>
                <p className="mt-2 flex items-center gap-2 text-sm text-muted">
                  <Clock size={16} className="shrink-0" />
                  {hora}
                </p>
              </section>

              {/* Lo practico va en el papel: es la lista que el cliente revisa la
                  noche antes del viaje, cuando ya no tiene la pagina abierta. */}
              <section className="mt-7 border-t border-border pt-6">
                <h2 className="flex items-center gap-2 font-sans text-sm font-medium tracking-tight text-foreground">
                  <Suitcase size={18} className="shrink-0 text-accent" />
                  {included.bringTitle}
                </h2>
                <ul className="mt-3 grid gap-2 text-sm leading-relaxed text-muted sm:grid-cols-2 print:grid-cols-2">
                  {included.bring.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="text-accent print:text-foreground">·</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </section>

              <button
                type="button"
                onClick={() => window.print()}
                className="mt-7 flex w-full items-center justify-center gap-2 rounded-xl border border-border-strong px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-surface print:hidden"
              >
                <DownloadSimple size={18} />
                {confirmation.downloadReceipt}
              </button>
            </div>
          </section>

          {/* --- Columna 2: lo que todavia puede pedir. Nunca se imprime. ---- */}
          <div className="flex flex-col gap-6 print:hidden">
            <section className="border border-border bg-background p-7 sm:p-8">
              <h2 className="flex items-center gap-2 font-sans text-sm font-medium tracking-tight text-foreground">
                <UserCheck size={18} className="shrink-0 text-accent" />
                {confirmation.agentHeadline}
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted">{confirmation.agentBody}</p>
            </section>

            {tieneWhatsapp && (
              <section className="border border-border bg-background p-7 sm:p-8">
                <h2 className="font-sans text-base font-medium tracking-tight text-foreground">
                  {confirmation.needsHeadline}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  {confirmation.needsIntro}
                </p>

                <ul className="mt-5 flex flex-col gap-2">
                  {confirmation.needs.map((need) => {
                    const Icono =
                      ICONO_SUGERENCIA[need.icon as keyof typeof ICONO_SUGERENCIA] ?? Question;

                    return (
                      <li key={need.icon}>
                        <a
                          href={whatsappHref(mensajeDeSugerencia(need.ask))}
                          target="_blank"
                          rel="noopener"
                          className="group flex gap-3 rounded-xl border border-transparent p-3 transition-colors hover:border-border hover:bg-surface"
                        >
                          <Icono
                            size={20}
                            className="mt-0.5 shrink-0 text-accent transition-transform group-hover:scale-110"
                          />
                          <span className="flex flex-col gap-0.5">
                            <span className="text-sm font-medium text-foreground">
                              {need.title}
                            </span>
                            <span className="text-xs leading-relaxed text-muted">{need.body}</span>
                          </span>
                        </a>
                      </li>
                    );
                  })}
                </ul>

                <a
                  href={whatsappHref(mensajeWhatsapp)}
                  target="_blank"
                  rel="noopener"
                  className="mt-5 flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 text-sm font-medium text-accent-foreground transition-transform hover:scale-[1.01] active:scale-[0.98]"
                >
                  <WhatsappLogo size={18} weight="fill" />
                  {confirmation.needsOther}
                </a>
              </section>
            )}

            <Link
              href={`/${lang}`}
              className="flex w-full items-center justify-center rounded-xl px-4 py-3 text-sm text-muted transition-colors hover:text-foreground"
            >
              {confirmation.backHome}
            </Link>
          </div>
        </div>

        <p className="mt-10 text-center text-xs text-muted print:hidden">
          {nav.brandMain} {nav.brandAccent} · {footer.city}
        </p>
      </main>
    </div>
  );
}
