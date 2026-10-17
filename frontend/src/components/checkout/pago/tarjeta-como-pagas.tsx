'use client';

import { useState } from 'react';
import { m, useReducedMotion } from 'framer-motion';
import { CheckCircle, Lock, Ticket, Warning } from '@phosphor-icons/react';
import Link from 'next/link';
import { BloqueDePaso, CheckoutSectionCard } from '@/components/checkout-section-card';
import { Despliegue } from '@/components/checkout/despliegue';
import { NotaSeguridadStripe } from '@/components/checkout/pago/nota-seguridad';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';
import { ErrorBlock } from '@/components/error-block';
import { ErrorDeCampo, FieldError, propsDeError } from '@/components/field-error';
import { Turnstile } from '@/components/turnstile';
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
  feedback,
  ayudaMensaje,
  onSubmit,
  onCaptchaToken,
}: StripePanelProps) {
  // Cerrado por default: la mayoria de las reservas no lleva codigo — una
  // correccion disponible para quien la busca, no la primera decision.
  const [promoAbierto, setPromoAbierto] = useState(false);
  const sinMovimiento = useReducedMotion();
  const pagoCreado = phase === 'payment';
  const abierta = phase !== 'payment' && phase !== 'unavailable';

  const resumen = [
    moneda,
    formaPagoDisponible !== false
      ? (formaPago === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit)
      : null,
  ].filter(Boolean).join(' · ');

  const cta = abierta ? (
    <m.button
      type="button"
      onClick={onSubmit}
      disabled={phase === 'submitting' || submitDisabled}
      animate={
        waiverAccepted && phase !== 'submitting' && !submitDisabled && !sinMovimiento
          ? {
              scale: [1, 1.045, 1],
              boxShadow: [
                '0 0 0 0 rgba(255,222,0,0)',
                '0 0 0 10px rgba(255,222,0,0.28)',
                '0 0 0 0 rgba(255,222,0,0)',
              ],
            }
          : { scale: 1, boxShadow: '0 0 0 0 rgba(255,222,0,0)' }
      }
      transition={
        waiverAccepted && phase !== 'submitting' && !submitDisabled && !sinMovimiento
          ? { duration: 1.4, repeat: 2, repeatDelay: 0.6, ease: 'easeInOut' }
          : { duration: 0.2 }
      }
      // Es donde de verdad se perdian los clientes: llenaban todo y el boton se
      // quedaba igual de quieto que el resto, sin nada que lo distinguiera como
      // "esto es lo que sigue". El pulso (se apaga solo tras 2 vueltas, con
      // fallback de opacidad en movimiento reducido) lo dispara `waiverAccepted`:
      // es lo unico que el cliente tiene que decidir antes de que sirva.
      className="inline-flex items-center justify-center gap-2 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-opacity disabled:opacity-60"
    >
      <Lock size={16} />
      {phase === 'submitting' ? checkout.submitting : (etiquetaBotonEnvio ?? checkout.payButton)}
    </m.button>
  ) : undefined;

  return (
    <>
      <CheckoutSectionCard
          title={checkout.howYouPay}
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
                  <div className="flex overflow-hidden rounded-full border border-border text-xs">
                    {(['MXN', 'USD'] as const).map((option) => (
                      <label
                        key={option}
                        aria-label={option === 'MXN' ? checkout.currency.mxn : checkout.currency.usd}
                        className="cursor-pointer px-3 py-1.5 font-medium text-muted transition-colors has-[:checked]:bg-foreground has-[:checked]:text-surface"
                      >
                        <input
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
                        className="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface"
                      >
                        <input
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
                    <p className="text-xs text-muted">{checkout.paymentMethod.depositNote}</p>
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
                    <button
                      type="button"
                      onClick={() => setPromoAbierto(true)}
                      className="inline-flex items-center gap-2 rounded-full border border-accent bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
                    >
                      <Ticket size={18} weight="fill" />
                      {checkout.promoCode.toggle}
                    </button>
                  </Despliegue>
                  <Despliegue abierto={promoAbierto || Boolean(codigoPromocional)}>
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="codigo-promocional" className="text-xs font-medium text-muted">
                        {checkout.promoCode.label}
                      </label>
                      <input
                        id="codigo-promocional"
                        type="text"
                        value={codigoPromocional}
                        disabled={phase === 'submitting'}
                        onChange={(e) => onCodigoPromocionalChange(e.target.value)}
                        placeholder={checkout.promoCode.placeholder}
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
                      />
                      <Despliegue abierto={promoEstado === 'verificando'}>
                        <p className="text-xs text-muted">{checkout.promoCode.checking}</p>
                      </Despliegue>
                      <Despliegue abierto={promoEstado === 'valido' && Boolean(promoPorcentaje)}>
                        <p className="flex items-center justify-between gap-3 text-xs text-exito">
                          <span className="flex items-center gap-1.5">
                            <CheckCircle size={14} weight="fill" />
                            {checkout.promoCode.valid.replace('{percent}', String(Number(promoPorcentaje ?? 0)))}
                          </span>
                          {/* Reversible: quitar vacia el campo y el descuento desaparece del resumen. */}
                          <button
                            type="button"
                            onClick={() => { onCodigoPromocionalChange(''); setPromoAbierto(false); }}
                            className="text-muted underline-offset-2 hover:text-foreground hover:underline"
                          >
                            {checkout.promoCode.remove}
                          </button>
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
                <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted">
                  <input
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
                <ErrorBlock
                  mensaje={error}
                  ayudaTitulo={feedback.helpTitle}
                  ayudaCta={feedback.helpCta}
                  ayudaMensaje={ayudaMensaje}
                />
              )}
            </>
          )}
      </CheckoutSectionCard>
      {abierta && <NotaSeguridadStripe checkout={checkout} />}
    </>
  );
}
