import Link from 'next/link';
import { CheckCircle, Clock, MapPin, Suitcase, UserCheck } from '@phosphor-icons/react/ssr';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SiteHeader } from '@/components/site-header';

type BookingConfirmationProps = {
  lang: Locale;
  dict: Dictionary;
  email: string;
  fecha: string;
  hora: string;
  personas: number;
  pagado: string;
  /** Lo que queda por pagar en efectivo, o null si pago el 100%. */
  saldoEnEfectivo: string | null;
  /** Etiquetas de lo que el agente todavia debe cotizar. */
  porCotizar: string[];
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
 */
export function BookingConfirmation({
  lang,
  dict,
  email,
  fecha,
  hora,
  personas,
  pagado,
  saldoEnEfectivo,
  porCotizar,
  procesando,
}: BookingConfirmationProps) {
  const { checkout, footer, nav, included } = dict;
  const { confirmation } = checkout;

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={nav} tone="plain" />

      <main className="mx-auto flex max-w-2xl flex-col px-6 py-12 sm:px-8">
      <div className="rounded-3xl border border-border bg-surface p-8 shadow-[0_18px_45px_rgba(11,36,32,0.16)] sm:p-10">
        <CheckCircle size={40} weight="fill" className="text-accent" />

        <h1 className="mt-5 text-2xl leading-tight font-medium tracking-tight text-foreground sm:text-3xl">
          {procesando ? confirmation.processingHeadline : confirmation.headline}
        </h1>

        <p className="mt-3 max-w-[55ch] text-sm leading-relaxed text-muted">
          {procesando
            ? confirmation.processingBody
            : confirmation.emailNotice.replace('{email}', email)}
        </p>

        <section className="mt-8 border-t border-border pt-6">
          <h2 className="text-sm font-medium tracking-tight text-foreground">
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
          <h2 className="flex items-center gap-2 text-sm font-medium tracking-tight text-foreground">
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

        <section className="mt-8 border-t border-border pt-6">
          <h2 className="flex items-center gap-2 text-sm font-medium tracking-tight text-foreground">
            <UserCheck size={18} className="shrink-0 text-accent" />
            {confirmation.agentHeadline}
          </h2>
          <p className="mt-3 max-w-[60ch] text-sm leading-relaxed text-muted">
            {confirmation.agentBody}
          </p>

          {/* Se repite aqui lo que NO esta pagado: es el punto donde el cliente
              todavia lo esta leyendo, y evita el reclamo el dia del viaje. */}
          {porCotizar.length > 0 && (
            <p className="mt-3 max-w-[60ch] rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm leading-relaxed text-foreground">
              {confirmation.quotesNote.replace('{items}', porCotizar.join(', '))}
            </p>
          )}
        </section>

        {/* Lo practico va aqui y no solo en la portada: es el momento en que el
            cliente de verdad esta pensando en su viaje. */}
        <section className="mt-8 border-t border-border pt-6">
          <h2 className="flex items-center gap-2 text-sm font-medium tracking-tight text-foreground">
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

          <div className="mt-5 rounded-xl border border-accent/40 bg-accent/10 px-4 py-3">
            <p className="text-sm font-medium text-foreground">
              {included.licenseTitle}
            </p>
            <p className="mt-1 max-w-[60ch] text-sm leading-relaxed text-foreground">
              {included.licenseBody}
            </p>
          </div>
        </section>

        <Link
          href={`/${lang}`}
          className="mt-8 flex w-full items-center justify-center rounded-xl bg-foreground px-4 py-3 text-sm font-medium text-surface transition-opacity hover:opacity-90"
        >
          {confirmation.backHome}
        </Link>
      </div>

        <p className="mt-6 text-center text-xs text-muted">
          {nav.brandMain} {nav.brandAccent} · {footer.city}
        </p>
      </main>
    </div>
  );
}
