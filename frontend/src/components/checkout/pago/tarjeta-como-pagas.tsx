'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, Lock, Ticket, Warning } from '@phosphor-icons/react';
import Link from 'next/link';
import { BloqueDePaso, CheckoutSectionCard } from '@/components/checkout-section-card';
import { useDeslindeEmpresas } from '@/components/checkout/deslinde-contexto';
import { hrefDeslinde } from '@/lib/routes';
import { Despliegue } from '@/components/ui/despliegue';
import { NotaSeguridadStripe } from '@/components/checkout/pago/nota-seguridad';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';
import { AvisoProblema } from '@/components/checkout/aviso-problema';
import { ErrorDeCampo, FieldError, propsDeError } from '@/components/ui/error-de-campo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Turnstile, turnstileEncendido, type EstadoVerificacion } from '@/components/turnstile';
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
  const empresasDeslinde = useDeslindeEmpresas();
  // Cerrado por default: la mayoria de las reservas no lleva codigo — una
  // correccion disponible para quien la busca, no la primera decision.
  const [promoAbierto, setPromoAbierto] = useState(false);
  const pagoCreado = phase === 'payment';
  const abierta = phase !== 'payment' && phase !== 'unavailable';
  // Turnstile responde una vez (token, o vacío si falló: el backend falla abierto). Si tarda más de
  // 8 s, el botón se libera igual y el servidor decide.
  const [verificado, setVerificado] = useState(!turnstileEncendido);
  useEffect(() => {
    if (verificado) return;
    const espera = setTimeout(() => setVerificado(true), 8000);
    return () => clearTimeout(espera);
  }, [verificado]);
  const alToken = (token: string) => {
    setVerificado(true);
    onCaptchaToken(token);
  };
  // La verificacion se trata como un campo mas: si Cloudflare pidio marcar la casilla y no se ha marcado,
  // «Pagar» no llama al servidor (que respondia con la tarjeta roja y WhatsApp); dice que falta, en la linea.
  const [captcha, setCaptcha] = useState<EstadoVerificacion>('esperando');
  const [intentoPagar, setIntentoPagar] = useState(false);
  const faltaMarcar = turnstileEncendido && captcha === 'visible';
  const verificando = turnstileEncendido && captcha !== 'visible' && !verificado;
  const mensajeVerificacion = faltaMarcar
    ? checkout.verificacion.marca
    : verificando ? checkout.barra.verificando : '';
  const alPagar = () => {
    if (mensajeVerificacion) {
      setIntentoPagar(true);
      return;
    }
    onSubmit();
  };

  // En móvil el botón vive en la barra inferior; en escritorio, en el pie de la tarjeta.
  const movil = useMovil();
  usePublicarAccion(movil && abierta ? {
    etiqueta: etiquetaBotonEnvio ?? checkout.barra.continuarTarjeta,
    alPulsar: alPagar,
    deshabilitado: submitDisabled || Boolean(mensajeVerificacion),
    razon: mensajeVerificacion || undefined,
    cargando: phase === 'submitting',
    etiquetaCargando: checkout.submitting,
  } : null, 'contenido');

  const cta = abierta && !movil ? (
    <Button
      onClick={alPagar}
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
          paso="pago"
          estado={pagoCreado ? 'completado' : 'activo'}
          pie={cta}
        >
          {phase === 'unavailable' && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 bg-cafe-bruma p-6 text-center">
              <Warning size={24} />
              <p className="texto-cuerpo">{checkout.paymentUnavailable}</p>
            </div>
          )}

          {abierta && (
            <>
              {/* Ya se precarga segun el idioma: una correccion disponible para
                  quien la busque, chica, no la primera decision del checkout. */}
              {usdDisponible && (
                <fieldset className="flex items-center justify-between gap-2" disabled={phase === 'submitting'}>
                  <legend className="sr-only">{checkout.currency.headline}</legend>
                  <span className="texto-cuerpo font-semibold">{checkout.currency.headline}</span>
                  <div className="flex gap-1 rounded-full bg-cafe-bruma p-1 texto-cuerpo">
                    {(['MXN', 'USD'] as const).map((option) => (
                      <label
                        key={option}
                        aria-label={option === 'MXN' ? checkout.currency.mxn : checkout.currency.usd}
                        className="inline-flex min-h-11 cursor-pointer items-center rounded-full px-4 font-semibold text-foreground transition-colors has-[:checked]:bg-tinta has-[:checked]:text-white has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring"
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
                        className="flex min-h-14 cursor-pointer items-center gap-3 border-2 border-transparent bg-cafe-bruma px-4 py-3 texto-cuerpo font-semibold text-foreground transition-colors has-[:checked]:border-tinta has-[:checked]:bg-superficie"
                      >
                        <Input
                          aspecto="heredado"
                          type="radio"
                          name="forma-pago"
                          checked={formaPago === option}
                          onChange={() => onFormaPagoChange(option)}
                          className="size-6 shrink-0 accent-tinta"
                        />
                        {option === 'completo' ? checkout.paymentMethod.full : checkout.paymentMethod.deposit}
                      </label>
                    ))}
                  </fieldset>
                  {/* La explicacion del anticipo solo cuando se elige: casi todos
                      pagan completo y no necesitan leerla. */}
                  <Despliegue abierto={formaPago === 'anticipo'}>
                    <p className="texto-cuerpo">{checkout.paymentMethod.depositNote}</p>
                  </Despliegue>
                </BloqueDePaso>
              )}

              {codigoPromocionalDisponible !== false && (
                <fieldset disabled={phase === 'submitting'}>
                  {/* Botón gris en píldora y no texto suelto: se tiene que ver a primera vista (el QA no lo
                      encontraba), pero sin competir con el botón de pagar. */}
                  <Despliegue abierto={!promoAbierto && !codigoPromocional}>
                    <Button
                      variante="libre"
                      type="button"
                      onClick={() => setPromoAbierto(true)}
                      className="inline-flex min-h-11 items-center gap-2 rounded-full bg-cafe-bruma px-5 texto-cuerpo font-semibold text-foreground transition-colors hover:bg-borde"
                    >
                      <Ticket size={18} weight="fill" />
                      {checkout.promoCode.toggle}
                    </Button>
                  </Despliegue>
                  <Despliegue abierto={promoAbierto || Boolean(codigoPromocional)}>
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="codigo-promocional" className="texto-cuerpo font-semibold">
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
                        className="min-h-12 w-full rounded-campo border border-borde-control bg-superficie px-4 texto-cuerpo text-foreground focus:border-tinta focus:outline-none sm:min-h-11"
                      />
                      <Despliegue abierto={promoEstado === 'verificando'}>
                        <p className="texto-cuerpo">{checkout.promoCode.checking}</p>
                      </Despliegue>
                      <Despliegue abierto={promoEstado === 'valido' && Boolean(promoPorcentaje)}>
                        <p className="flex items-center justify-between gap-3 texto-cuerpo text-exito">
                          <span className="flex items-center gap-1.5">
                            <CheckCircle size={14} weight="fill" />
                            {checkout.promoCode.valid.replace('{percent}', String(Number(promoPorcentaje ?? 0)))}
                          </span>
                          {/* Reversible: quitar vacia el campo y el descuento desaparece del resumen. */}
                          <Button
                            variante="libre"
                            type="button"
                            onClick={() => { onCodigoPromocionalChange(''); setPromoAbierto(false); }}
                            className="inline-flex min-h-11 items-center text-foreground underline underline-offset-2 hover:text-cafe"
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
                <label className="flex items-start gap-3 texto-cuerpo text-foreground">
                  <Input
                    aspecto="heredado"
                    type="checkbox"
                    checked={waiverAccepted}
                    disabled={phase === 'submitting'}
                    onChange={(e) => onWaiverChange(e.target.checked)}
                    {...propsDeError('error-waiver', errorWaiver)}
                    className="mt-0.5 size-6 shrink-0 accent-tinta"
                  />
                  <span>
                    {checkout.waiver.accept}{' '}
                    <Link
                      href={hrefDeslinde(lang, empresasDeslinde)}
                      target="_blank"
                      rel="noopener"
                      className="font-semibold underline underline-offset-2"
                    >
                      {checkout.waiver.linkLabel}
                    </Link>{' '}
                    {checkout.waiver.and}{' '}
                    <Link
                      href={`/${lang}/privacidad`}
                      target="_blank"
                      rel="noopener"
                      className="font-semibold underline underline-offset-2"
                    >
                      {checkout.waiver.privacyLinkLabel}
                    </Link>
                    .
                  </span>
                </label>
                <ErrorDeCampo id="error-waiver" mensaje={errorWaiver ? checkout.waiver.missing : ''} />
              </div>

              {/* El widget solo aparece si Cloudflare decide preguntar algo; su mensaje va en la linea, como el de
                  cualquier otro campo. `tabIndex` deja que el error lleve el foco aqui al aparecer. */}
              <div id="verificacion" aria-describedby="error-verificacion" tabIndex={-1} className="outline-none">
                <Turnstile onToken={alToken} onEstado={setCaptcha} />
              </div>
              <ErrorDeCampo id="error-verificacion" mensaje={intentoPagar ? mensajeVerificacion : ''} />

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
