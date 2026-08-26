'use client';

import Link from 'next/link';
import {
  CheckCircle,
  Clock,
  DownloadSimple,
  MapPin,
  Suitcase,
  UserCheck,
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

/**
 * Pantalla que reemplaza al checkout cuando el pago pasa.
 *
 * Es pantalla completa y no un modal a proposito: ya no hay nada atras a lo que
 * volver, y esto es el comprobante que el cliente va a capturar o enseñar en el
 * muelle. La reserva la marca pagada el webhook de Stripe, no esta vista — aqui
 * solo se le informa al cliente lo que acaba de pasar.
 *
 * El boton "Descargar recibo" es `window.print()`, no un PDF generado aparte:
 * sin backend nuevo, sin exponer una ruta que busque una reserva ajena por id
 * (justo el hueco que se cerro en `crear-pago`, ver ENDURECIMIENTO.md) y
 * cualquier navegador deja "Guardar como PDF" desde el dialogo de impresion.
 * Las clases `print:` deciden que va en ese papel y que no.
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

  const mensajeWhatsapp = confirmation.whatsappMessage
    .replace('{nombre}', nombre)
    .replace('{fecha}', fecha)
    .replace('{folio}', String(numeroDeConfirmacion));

  return (
    <div className="min-h-dvh bg-background print:bg-white">
      <div className="print:hidden">
        <SiteHeader lang={lang} nav={nav} />
      </div>

      <main className="mx-auto flex max-w-2xl flex-col px-6 py-12 sm:px-8 print:p-0">
        <div className="border border-border bg-surface p-8 shadow-[0_18px_45px_rgba(11,36,32,0.16)] sm:p-10 print:border-0 print:p-0 print:shadow-none">
          {/* Encabezado del recibo — solo aparece en la impresion, donde no hay
              SiteHeader ni el saludo de pantalla que lo sustituye. */}
          <div className="hidden print:mb-8 print:block">
            <p className="text-lg font-semibold text-foreground">
              {nav.brandMain} {nav.brandAccent}
            </p>
            <p className="text-sm text-muted">
              {confirmation.receiptTitle} · {confirmation.referenceLabel} #{numeroDeConfirmacion}
            </p>
          </div>

          <div className="flex flex-col items-center text-center print:items-start print:text-left">
            {/* `motion-safe` no hace falta aqui: `prefers-reduced-motion: reduce`
                ya colapsa cualquier animacion a 0.01ms en globals.css. */}
            <CheckCircle
              size={64}
              weight="fill"
              className="text-accent [animation:confirmacion-pop_0.5s_cubic-bezier(0.16,1,0.3,1)_both] print:hidden"
            />

            <h1 className="mt-5 text-2xl leading-tight text-foreground sm:text-3xl print:mt-0 print:text-xl">
              {procesando ? confirmation.processingHeadline : confirmation.headline}
            </h1>

            <p className="mt-2 text-xs font-medium tracking-wide text-muted print:hidden">
              {confirmation.referenceLabel} #{numeroDeConfirmacion}
            </p>

            <p className="mt-3 max-w-[55ch] text-sm leading-relaxed text-muted print:max-w-none">
              {procesando
                ? confirmation.processingBody
                : confirmation.emailNotice.replace('{email}', email)}
            </p>
          </div>

          <section className="mt-8 border-t border-border pt-6">
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

          <section className="mt-8 border-t border-border pt-6">
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

          <section className="mt-8 border-t border-border pt-6 print:hidden">
            <h2 className="flex items-center gap-2 font-sans text-sm font-medium tracking-tight text-foreground">
              <UserCheck size={18} className="shrink-0 text-accent" />
              {confirmation.agentHeadline}
            </h2>
            <p className="mt-3 max-w-[60ch] text-sm leading-relaxed text-muted">
              {confirmation.agentBody}
            </p>
          </section>

          {/* Lo practico va aqui y no solo en la portada: es el momento en que el
              cliente de verdad esta pensando en su viaje. */}
          <section className="mt-8 border-t border-border pt-6">
            <h2 className="flex items-center gap-2 font-sans text-sm font-medium tracking-tight text-foreground">
              <Suitcase size={18} className="shrink-0 text-accent" />
              {included.bringTitle}
            </h2>
            <ul className="mt-3 flex flex-col gap-2 text-sm leading-relaxed text-muted">
              {included.bring.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-accent">·</span>
                  {item}
                </li>
              ))}
            </ul>
          </section>

          {/* No queda hueco de datos abajo, solo pantalla: nada de esto tiene
              sentido en el papel del recibo. */}
          <div className="mt-8 flex flex-col gap-3 sm:flex-row print:hidden">
            {tieneWhatsapp && (
              <a
                href={whatsappHref(mensajeWhatsapp)}
                target="_blank"
                rel="noopener"
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 text-sm font-medium text-accent-foreground transition-transform hover:scale-[1.01] active:scale-[0.98]"
              >
                <WhatsappLogo size={18} weight="fill" />
                {confirmation.whatsappCta}
              </a>
            )}
            <button
              type="button"
              onClick={() => window.print()}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-border px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-background"
            >
              <DownloadSimple size={18} />
              {confirmation.downloadReceipt}
            </button>
          </div>

          <Link
            href={`/${lang}`}
            className="mt-3 flex w-full items-center justify-center rounded-xl px-4 py-3 text-sm text-muted transition-colors hover:text-foreground print:hidden"
          >
            {confirmation.backHome}
          </Link>
        </div>

        <p className="mt-6 text-center text-xs text-muted print:hidden">
          {nav.brandMain} {nav.brandAccent} · {footer.city}
        </p>
      </main>
    </div>
  );
}
