'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { CheckCircle, Clock, DownloadSimple, WhatsappLogo } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CabeceraMinima } from '@/components/reserva/cabecera-minima';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';
import { botonClases } from '@/components/ui/variantes';
import type { ColorActividad } from '@/lib/color-actividad';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

/** Un cobro de una reserva con varias empresas: quién cobra, cuánto y cómo va. */
export type CobroConfirmado = { empresa: string; monto: string };

/** Lo que muestra la confirmación; cada checkout lo arma con lo que sabe y deja vacío lo que no. */
export type DatosConfirmacion = {
  /** Folio de la reserva (o de la orden, en un paquete de varias empresas). */
  folio: number;
  /** Stripe tarda en acreditar según el método: mientras tanto no se dice «confirmada». */
  procesando: boolean;
  nombre: string;
  email: string;
  /** Mar, traslado o estancia: pinta el campo de arriba. */
  color: ColorActividad;
  /** Qué compró: el servicio o el paquete. */
  titulo: string;
  /** Las empresas que lo operan. */
  empresas: string[];
  /** Fecha de la reserva, para el mensaje de WhatsApp. */
  fecha: string;
  /** Los datos del viaje, uno por renglón (día, hora, personas…). */
  lineas: { etiqueta: string; valor: string }[];
  /** Un paquete: cada servicio con su día y sus personas. */
  componentes?: { titulo: string; detalle: string }[];
  /** Extras comprados, ya formateados. Vacío en una reserva repuesta: ahí solo se sabe lo cobrado. */
  extras: { label: string; amount: string }[];
  /** Cruza-empresa: cada cobro por separado. Con una sola empresa no se pinta. */
  cobros?: CobroConfirmado[];
  /** Lo cobrado hoy, con su moneda. */
  pagado: string | null;
  /** Lo que queda por pagar en efectivo el día del viaje; `null` si se pagó todo. */
  saldoEnEfectivo: string | null;
  /** Dónde y a qué hora se ven, solo si se sabe; si no, el asesor lo confirma. */
  encuentro: { lugar: string; hora?: string } | null;
  /** Qué llevar, solo si hay lista para este producto. */
  llevar?: string[];
};

type Props = {
  lang: Locale;
  dict: Dictionary;
  datos: DatosConfirmacion;
};

// Clases completas para que Tailwind las vea. El coral lleva el hondo: sobre el coral claro, el texto
// de 20 px no llega a 4,5:1. Mientras el pago se procesa el campo es negro, no el de la actividad: no
// se parece a una confirmación.
const CAMPO: Record<ColorActividad | 'procesando', string> = {
  mar: 'bg-azul',
  traslado: 'bg-coral-hondo',
  estancia: 'bg-verde',
  procesando: 'bg-tinta',
};

const SIGUE: Record<ColorActividad | 'paquete', keyof Dictionary['checkout']['confirmation']> = {
  mar: 'nextMar',
  traslado: 'nextTraslado',
  estancia: 'nextEstancia',
  paquete: 'nextPaquete',
};

/**
 * La confirmación de una reserva (F10), una sola para pesca, tour, hospedaje, traslado y paquetes de una o
 * dos empresas. Reemplaza al checkout en el mismo montaje: ya no hay nada atrás a lo que volver, y esto
 * es el comprobante (no hay cuentas; el otro es el correo).
 *
 * El primer cuadro responde si quedó, cuál es el folio y qué se compró, en tipografía grande sobre el
 * campo de color de la actividad. Debajo, a la izquierda lo que se reservó y el dinero (lo que se
 * pagó hoy y, aparte, lo que se paga en efectivo); a la derecha lo que sigue y las garantías. Una acción
 * primaria (guardar el comprobante, `window.print()`: sin ruta nueva que busque una reserva por id) y
 * una secundaria (WhatsApp con el folio escrito). Lo que se imprime es todo menos las acciones.
 *
 * Solo dice lo que es verdad: «confirmada» únicamente con el pago aplicado, la asignación de panga,
 * capitán o vehículo como pendiente, y cada cobro de cruza-empresa con su empresa.
 */
export function ConfirmacionReserva({ lang, dict, datos }: Props) {
  const { checkout, sedeContenido, included } = dict;
  const { confirmation } = checkout;
  const garantias = sedeContenido.tranquilidad;
  const esPaquete = Boolean(datos.componentes?.length);

  // La confirmación no es una página nueva: reemplaza al checkout en el mismo montaje, así que el
  // navegador conserva el scroll del formulario. Salto directo y sin animar.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, []);

  const mensajeWhatsapp = confirmation.whatsappMessage
    .replace('{nombre}', datos.nombre)
    .replace('{fecha}', datos.fecha)
    .replace('{folio}', String(datos.folio));

  const sigue = confirmation[SIGUE[esPaquete ? 'paquete' : datos.color]] as string;
  const avisoCorreo = (datos.procesando ? confirmation.processingBody : confirmation.emailNotice).replace('{email}', datos.email);

  return (
    <div className="flex min-h-dvh flex-col bg-background print:bg-white">
      <div className="print:hidden">
        <CabeceraMinima lang={lang} nav={dict.nav} volverHref={`/${lang}`} volverLabel={checkout.back} />
      </div>

      <main className="flex-1">
        <section className={cn('text-hero-ink print:bg-white print:text-foreground', CAMPO[datos.procesando ? 'procesando' : datos.color])}>
          <div className="mx-auto max-w-[1440px] px-4 pb-12 pt-[calc(var(--nav-alto)+3rem)] sm:px-6 lg:px-12 lg:pb-16 lg:pt-[calc(var(--nav-alto)+4rem)] print:pt-8">
            <div className="flex flex-wrap items-end justify-between gap-x-12 gap-y-6">
              <h1 className="max-w-[14ch] texto-grande">
                {datos.procesando ? confirmation.processingHeadline : confirmation.headline}
              </h1>
              <p className="flex flex-col">
                <span className="texto-etiqueta">{confirmation.referenceLabel}</span>
                <span className="texto-grande tabular-nums">#{datos.folio}</span>
              </p>
            </div>
            <p className="mt-6 max-w-[58ch] text-xl leading-snug">{avisoCorreo}</p>
            <p className="mt-8 texto-subtitulo">
              {datos.titulo}
              {datos.empresas.length > 0 && <span className="font-normal">{` · ${datos.empresas.join(' + ')}`}</span>}
            </p>
          </div>
        </section>

        <div className="mx-auto grid max-w-[1440px] gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.15fr_1fr] lg:gap-20 lg:px-12 lg:py-20 print:block print:py-6">
          <div className="flex flex-col gap-12">
            <section>
              <h2 className="texto-paso">{confirmation.tripHeadline}</h2>
              <dl className="mt-6 flex flex-col gap-3">
                {datos.lineas.map((linea) => (
                  <div key={linea.etiqueta} className="flex items-baseline justify-between gap-6 texto-cuerpo">
                    <dt className="font-semibold">{linea.etiqueta}</dt>
                    <dd className="text-right first-letter:capitalize">{linea.valor}</dd>
                  </div>
                ))}
                {datos.extras.map((extra) => (
                  <div key={extra.label} className="flex items-baseline justify-between gap-6 texto-cuerpo">
                    <dt className="min-w-0">{extra.label}</dt>
                    <dd className="text-right tabular-nums">{extra.amount}</dd>
                  </div>
                ))}
              </dl>
              {datos.componentes && datos.componentes.length > 0 && (
                <ul className="mt-6 flex flex-col gap-2">
                  {datos.componentes.map((c) => (
                    <li key={c.titulo} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 bg-cafe-bruma px-5 py-4 texto-cuerpo">
                      <span className="font-semibold">{c.titulo}</span>
                      <span>{c.detalle}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h2 className="texto-paso">{confirmation.moneyHeadline}</h2>
              {datos.cobros && datos.cobros.length > 1 && (
                <ul className="mt-6 flex flex-col gap-2">
                  {datos.cobros.map((cobro) => (
                    <li key={cobro.empresa} className="flex items-center justify-between gap-4 bg-cafe-bruma px-5 py-4">
                      <span className="min-w-0 texto-cuerpo font-semibold">{cobro.empresa}</span>
                      <span className="flex shrink-0 flex-col items-end">
                        <span className="texto-cuerpo font-semibold tabular-nums">{cobro.monto}</span>
                        <span className="flex items-center gap-1 texto-cuerpo text-exito">
                          {datos.procesando ? <Clock size={16} weight="bold" aria-hidden /> : <CheckCircle size={16} weight="bold" aria-hidden />}
                          {datos.procesando ? confirmation.chargeProcessing : confirmation.chargePaid}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-6 flex flex-col gap-2">
                {datos.pagado && (
                  <p className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 bg-tinta px-5 py-4 text-hero-ink">
                    <span className="texto-etiqueta">{confirmation.paidLabel}</span>
                    <span className="texto-paso tabular-nums">{datos.pagado}</span>
                  </p>
                )}
                {datos.saldoEnEfectivo && (
                  <p className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 bg-cafe-claro px-5 py-4 text-tinta">
                    <span className="texto-etiqueta">{confirmation.pendingLabel}</span>
                    <span className="texto-paso tabular-nums">{datos.saldoEnEfectivo}</span>
                  </p>
                )}
              </div>
            </section>
          </div>

          <div className="flex flex-col gap-12">
            <section>
              <h2 className="texto-paso">{confirmation.nextHeadline}</h2>
              <div className="mt-6 flex flex-col gap-6 texto-cuerpo">
                <p>{sigue}</p>
                {datos.encuentro && (
                  <div>
                    <h3 className="texto-etiqueta">{confirmation.meetingHeadline}</h3>
                    <p className="mt-1">{datos.encuentro.lugar}</p>
                    {datos.encuentro.hora && <p>{datos.encuentro.hora}</p>}
                  </div>
                )}
                {datos.llevar && datos.llevar.length > 0 && (
                  <div>
                    <h3 className="texto-etiqueta">{included.bringTitle}</h3>
                    <ul className="mt-1 flex flex-col gap-1">
                      {datos.llevar.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </section>

            <section>
              <h2 className="texto-paso">{confirmation.guaranteesHeadline}</h2>
              <ul className="mt-6 flex flex-col gap-2">
                <li className="bg-cafe-bruma px-5 py-4">
                  <h3 className="texto-etiqueta">{garantias.climaTitulo}</h3>
                  <p className="mt-1 texto-cuerpo">{garantias.climaTexto}</p>
                </li>
                <li className="bg-cafe-bruma px-5 py-4">
                  <h3 className="texto-etiqueta">{garantias.fechaTitulo}</h3>
                  <p className="mt-1 texto-cuerpo">{garantias.fechaTexto}</p>
                </li>
              </ul>
            </section>

            <div className="flex flex-col items-start gap-3 print:hidden">
              <Button onClick={() => window.print()}>
                <DownloadSimple size={20} weight="bold" aria-hidden="true" />
                {confirmation.saveReceipt}
              </Button>
              {tieneWhatsapp && (
                <a
                  href={whatsappHref(mensajeWhatsapp)}
                  target="_blank"
                  rel="noopener"
                  className={botonClases({ variante: 'campana-gris' })}
                >
                  <WhatsappLogo size={20} weight="fill" aria-hidden="true" />
                  {confirmation.whatsappCta}
                </a>
              )}
              <Link href={`/${lang}`} className="inline-flex min-h-11 items-center texto-cuerpo underline underline-offset-4 transition-colors hover:text-cafe">
                {confirmation.backHome}
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
