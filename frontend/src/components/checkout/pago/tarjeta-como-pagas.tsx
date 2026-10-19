'use client';

import { rotuloDePaso } from '@/lib/pasos-checkout';
import { useState } from 'react';
import { CheckCircle, Lock, Ticket, Warning } from '@phosphor-icons/react';
import Link from 'next/link';
import { BloqueDePaso, CheckoutSectionCard } from '@/components/checkout-section-card';
import { Despliegue } from '@/components/ui/despliegue';
import { NotaSeguridadStripe } from '@/components/checkout/pago/nota-seguridad';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';
import { AvisoProblema } from '@/components/checkout/aviso-problema';
import { ErrorDeCampo, FieldError, propsDeError } from '@/components/ui/error-de-campo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Turnstile } from '@/components/turnstile';
import { usePublicarAccion } from '@/components/reserva/contexto-barra';
import { useMovil } from '@/components/reserva/use-movil';
import { WaitNotice } from '@/components/wait-notice';

/**
 * El cuarto paso antes de que exista el pago: cómo paga el cliente (moneda,
 * modalidad, código promocional), el deslinde y el botón que crea el pago.
 * Vive en la columna de pasos (ver `destinoTarjeta`); al crearse el pago se
 * pliega a un renglón y debajo aparece el formulario de tarjeta (`FormularioPago`).
 */
export function TarjetaComoPagas({
  lang,
  checkout,
  waiverAccepted,
  onWaiverChange,
  errorWaiver,
  moneda,
  onMonedaChange,
  usdDisponible,
  formaPago,
  onFormaPagoChange,
  formaPagoDisponible = true,
  codigoPromocional,
  onCodigoPromocionalChange,
  codigoPromocionalDisponible = true,
  promoEstado,
  promoPorcentaje,
  avisoCargos,
  etiquetaBotonEnvio,
  submitDisabled = false,
  phase,
  error,
  errorTipo,
  onProblema,
  feedback,
  ayudaMensaje,
  onSubmit,
  onCaptchaToken,
}: StripePanelProps) {
  // Cerrado por default: la mayoria de las reservas no lleva codigo — una
  // correccion disponible para quien la busca, no la primera decision.
  const [promoAbierto, setPromoAbierto] = useState(false);
  const pagoCreado = phase === 'payment';
  const abierta = phase !== 'payment' && phase !== 'unavailable';
  // En móvil el botón vive en la barra inferior; en escritorio, en el pie de la tarjeta.
  const movil = useMovil();
  usePublicarAccion(movil && abierta ? {
    etiqueta: etiquetaBotonEnvio ?? checkout.barra.continuarTarjeta,
    alPulsar: onSubmit,
    deshabilitado: submitDisabled,
    cargando: phase === 'submitting',
    etiquetaCargando: checkout.submitting,
  } : null, 'contenido');

  const resumen = [
    moneda,
    formaPagoDisponible !== false
      ? (formaPago === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit)
      : null,
  ].filter(Boolean).join(' · ');

  const cta = abierta && !movil ? (
    <Button
      onClick={onSubmit}
      disabled={submitDisabled}
      cargando={phase === 'submitting'}
      etiquetaCargando={checkout.submitting}
    >
      <Lock size={20} weight="bold" aria-hidden="true" />
      {etiquetaBotonEnvio ?? checkout.payButton}
    </Button>
  ) : undefined;

  return (
    <>
      <CheckoutSectionCard
          title={checkout.howYouPay}
          pasoRotulo={rotuloDePaso(checkout.stepper.stepOf, 'pago')}
          estado={pagoCreado ? 'completado' : 'activo'}
          resumen={resumen}
          pie={cta}
        >
          {phase === 'unavailable' && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 border border-dashed border-border p-6 text-center">
              <Warning size={20} className="text-muted" />
              <p className="text-sm text-muted">{checkout.paymentUnavailable}</p>
            </div>
          )}

          {abierta && (
            <>
              {/* Ya se precarga segun el idioma: una correccion disponible para
                  quien la busque, chica, no la primera decision del checkout. */}
              {usdDisponible && (
                <fieldset className="flex items-center justify-between gap-2" disabled={phase === 'submitting'}>
                  <legend className="sr-only">{checkout.currency.headline}</legend>
                  <span className="text-sm text-muted">{checkout.currency.headline}</span>
                  <div className="flex overflow-hidden rounded-full border border-border text-sm">
                    {(['MXN', 'USD'] as const).map((option) => (
                      <label
                        key={option}
                        aria-label={option === 'MXN' ? checkout.currency.mxn : checkout.currency.usd}
                        className="cursor-pointer px-3 py-1.5 font-medium text-muted transition-colors has-[:checked]:bg-foreground has-[:checked]:text-cafe-bruma"
                      >
                        <Input
                          aspecto="heredado"
                          type="radio"
                          name="moneda"
                          checked={moneda === option}
                          onChange={() => onMonedaChange(option)}
                          className="sr-only"
                        />
                        {option}
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}

              {formaPagoDisponible !== false && (
                <BloqueDePaso titulo={checkout.paymentMethod.headline}>
                  <fieldset className="grid gap-3 sm:grid-cols-2" disabled={phase === 'submitting'}>
                    <legend className="sr-only">{checkout.paymentMethod.headline}</legend>
                    {(['completo', 'anticipo'] as const).map((option) => (
                      <label
                        key={option}
                        className="flex cursor-pointer items-center gap-3 rounded-campo border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-cafe-medio has-[:checked]:bg-cafe-bruma"
                      >
                        <Input
                          aspecto="heredado"
                          type="radio"
                          name="forma-pago"
                          checked={formaPago === option}
                          onChange={() => onFormaPagoChange(option)}
                          className="h-4 w-4 shrink-0 accent-accent"
                        />
                        {option === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit}
                      </label>
                    ))}
                  </fieldset>
                  {/* La explicacion del anticipo solo cuando se elige: casi todos
                      pagan completo y no necesitan leerla. */}
                  <Despliegue abierto={formaPago === 'anticipo'}>
                    <p className="text-sm text-muted">{checkout.paymentMethod.depositNote}</p>
                  </Despliegue>
                </BloqueDePaso>
              )}

              {codigoPromocionalDisponible !== false && (
                <fieldset disabled={phase === 'submitting'}>
                  {/* Boton con borde y no texto suelto: se tiene que ver a primera
                      vista (el QA no lo encontraba), pero en el color de acento (indigo) con un tinte suave, no
                      en el amarillo de accion, para llamar la atencion sin competir con el
                      boton de pagar. */}
                  <Despliegue abierto={!promoAbierto && !codigoPromocional}>
                    <Button
                      variante="libre"
                      type="button"
                      onClick={() => setPromoAbierto(true)}
                      className="inline-flex items-center gap-2 rounded-full border border-accent bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
                    >
                      <Ticket size={18} weight="fill" />
                      {checkout.promoCode.toggle}
                    </Button>
                  </Despliegue>
                  <Despliegue abierto={promoAbierto || Boolean(codigoPromocional)}>
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="codigo-promocional" className="text-sm font-medium text-muted">
                        {checkout.promoCode.label}
                      </label>
                      <Input
                        aspecto="heredado"
                        id="codigo-promocional"
                        type="text"
                        value={codigoPromocional}
                        disabled={phase === 'submitting'}
                        onChange={(e) => onCodigoPromocionalChange(e.target.value)}
                        placeholder={checkout.promoCode.placeholder}
                        className="w-full rounded-campo border border-border bg-superficie px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
                      />
                      <Despliegue abierto={promoEstado === 'verificando'}>
                        <p className="text-sm text-muted">{checkout.promoCode.checking}</p>
                      </Despliegue>
                      <Despliegue abierto={promoEstado === 'valido' && Boolean(promoPorcentaje)}>
                        <p className="flex items-center justify-between gap-3 text-sm text-exito">
                          <span className="flex items-center gap-1.5">
                            <CheckCircle size={14} weight="fill" />
                            {checkout.promoCode.valid.replace('{percent}', String(Number(promoPorcentaje ?? 0)))}
                          </span>
                          {/* Reversible: quitar vacia el campo y el descuento desaparece del resumen. */}
                          <Button
                            variante="libre"
                            type="button"
                            onClick={() => { onCodigoPromocionalChange(''); setPromoAbierto(false); }}
                            className="text-muted underline-offset-2 hover:text-foreground hover:underline"
                          >
                            {checkout.promoCode.remove}
                          </Button>
                        </p>
                      </Despliegue>
                      <Despliegue abierto={promoEstado === 'invalido'}>
                        <FieldError id="codigo-promocional-error" mensaje={checkout.promoCode.invalid} />
                      </Despliegue>
                    </div>
                  </Despliegue>
                </fieldset>
              )}

              {avisoCargos}

              {/* Deslinde y aviso de privacidad: una sola casilla para los dos
                  documentos porque es un solo consentimiento; el texto completo de
                  cada uno vive en su pagina y abre en otra pestaña para no tirar lo
                  que el cliente ya lleno. */}
              <div>
                <label className="flex items-start gap-2.5 text-sm leading-relaxed text-muted">
                  <Input
                    aspecto="heredado"
                    type="checkbox"
                    checked={waiverAccepted}
                    disabled={phase === 'submitting'}
                    onChange={(e) => onWaiverChange(e.target.checked)}
                    {...propsDeError('error-waiver', errorWaiver)}
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-accent"
                  />
                  <span>
                    {checkout.waiver.accept}{' '}
                    <Link
                      href={`/${lang}/deslinde`}
                      target="_blank"
                      rel="noopener"
                      className="text-foreground underline underline-offset-2"
                    >
                      {checkout.waiver.linkLabel}
                    </Link>{' '}
                    {checkout.waiver.and}{' '}
                    <Link
                      href={`/${lang}/privacidad`}
                      target="_blank"
                      rel="noopener"
                      className="text-foreground underline underline-offset-2"
                    >
                      {checkout.waiver.privacyLinkLabel}
                    </Link>
                    .
                  </span>
                </label>
                <ErrorDeCampo id="error-waiver" mensaje={errorWaiver ? checkout.waiver.missing : ''} />
              </div>

              <Turnstile onToken={onCaptchaToken} />

              {phase === 'submitting' && <WaitNotice mensaje={feedback.savingWait} />}

              {phase === 'error' && error && (
                <AvisoProblema
                  checkout={checkout}
                  feedback={feedback}
                  tipo={errorTipo ?? 'red'}
                  mensaje={error}
                  ayudaMensaje={ayudaMensaje}
                  alAccionar={(clave) => {
                    // Reintentar, otra tarjeta y volver a apartar vuelven a pedir el cobro; lo demás lo resuelve la vista.
                    if (clave === 'reintentar' || clave === 'otra_tarjeta' || clave === 'reapartar') onSubmit();
                    else onProblema?.(clave);
                  }}
                />
              )}
            </>
          )}
      </CheckoutSectionCard>
      {abierta && <NotaSeguridadStripe checkout={checkout} />}
    </>
  );
}
