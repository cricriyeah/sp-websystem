// Reglas puras de la pantalla de fallo del pedido: qué motivo mostrar, de qué
// empresa fue, y cuándo ofrecer ayuda humana. Sin React ni red.

export type ClaveMotivoRechazo =
  | 'insufficient_funds' | 'card_declined' | 'expired_card'
  | 'incorrect_cvc' | 'authentication_required' | 'generic';

/** Traduce el código que Stripe da en `card_error` a una clave de diccionario propia. */
export function claveMotivoRechazo(codigo?: string): ClaveMotivoRechazo {
  switch (codigo) {
    case 'insufficient_funds': return 'insufficient_funds';
    case 'expired_card': return 'expired_card';
    case 'incorrect_cvc':
    case 'invalid_cvc': return 'incorrect_cvc';
    case 'authentication_required': return 'authentication_required';
    case 'card_declined':
    case 'generic_decline': return 'card_declined';
    default: return 'generic';
  }
}

const FALLO_CAPTURA = /^no se pudo capturar (\S+)$/;

/** El servidor dice `no se pudo capturar <slug>` cuando falla la captura de una empresa. */
export function empresaDeFalloCaptura(motivo: string): string | null {
  return FALLO_CAPTURA.exec(motivo)?.[1] ?? null;
}

export const FALLOS_PARA_OFRECER_AYUDA = 3;

export function ofreceAyuda(fallos: number): boolean {
  return fallos >= FALLOS_PARA_OFRECER_AYUDA;
}

/** Pagos que ya estaban retenidos cuando la tarjeta fue rechazada en `indiceRechazo`. */
export function pagosRetenidosAntes<T>(pagos: T[], indiceRechazo: number | null): T[] {
  return indiceRechazo === null ? [] : pagos.slice(0, indiceRechazo);
}
