import type { ReactNode } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda } from '@/lib/api';

export type OrderLine = {
  label: string;
  amount: string;
};

export type Phase = 'form' | 'submitting' | 'payment' | 'unavailable' | 'error';

export type StripePanelProps = {
  lang: Locale;
  checkout: Dictionary['checkout'];
  waiverAccepted: boolean;
  onWaiverChange: (value: boolean) => void;
  errorWaiver: boolean;
  lines: OrderLine[];
  /** Quién opera lo que se compra: un sello por empresa, al abrir el resumen (sin foto de catálogo, Task 9.0). */
  sellos?: { nombre: string; logo?: string }[];
  /** Lo elegido en el viaje (fecha, hora, personas…), vivo desde el paso 1. */
  lineasViaje?: { etiqueta: string; valor: string }[];
  /**
   * Dónde se pinta la tarjeta "Cómo pagas" (moneda, modalidad, promo, deslinde y
   * el botón que crea el pago): en la columna de pasos, como el cuarto paso. El
   * panel conserva todo el estado y las props; solo el DOM de esa tarjeta vive
   * en otra columna (portal). `null` = todavía no se llegó al paso 4.
   */
  destinoTarjeta?: HTMLElement | null;
  /** En móvil el resumen ya se pintó arriba del formulario de pago (`FranjaResumen`): aquí no se repite. */
  resumenSoloEscritorio?: boolean;
  total: string;
  amountDueNow: string;
  moneda: Moneda;
  onMonedaChange: (value: Moneda) => void;
  usdDisponible: boolean;
  formaPago: 'completo' | 'anticipo';
  onFormaPagoChange: (value: 'completo' | 'anticipo') => void;
  formaPagoDisponible?: boolean;
  codigoPromocional: string;
  onCodigoPromocionalChange: (value: string) => void;
  codigoPromocionalDisponible?: boolean;
  promoEstado: 'idle' | 'verificando' | 'valido' | 'invalido';
  promoPorcentaje: string | null;
  avisoCargos?: ReactNode;
  etiquetaBotonEnvio?: string;
  submitDisabled?: boolean;
  phase: Phase;
  error: string;
  feedback: Dictionary['feedback'];
  /** Mensaje ya redactado para la vendedora, con la fecha y el grupo del cliente. */
  ayudaMensaje: string;
  onSubmit: () => void;
  /** Token del widget de Turnstile, montado aqui mismo (ver mas abajo). */
  onCaptchaToken: (token: string) => void;
};
