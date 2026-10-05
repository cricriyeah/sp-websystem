// Cuándo ofrecer ayuda humana (WhatsApp) mientras el cliente llena el checkout.
// Sin React ni red. La salida de emergencia de un pago rechazado ya existe
// (`fallo-pago.ts`, `ErrorBlock`); esto cubre el llenado: errores repetidos al
// confirmar un paso y choques con el tope de personas.

export type TipoTropiezo = 'validacion' | 'tope-personas';

export type EstadoAyuda = {
  validacion: number;
  topePersonas: number;
  descartada: boolean;
};

export const TROPIEZOS_PARA_OFRECER_AYUDA = 3;

export const ayudaInicial: EstadoAyuda = { validacion: 0, topePersonas: 0, descartada: false };

export function registrarTropiezo(estado: EstadoAyuda, tipo: TipoTropiezo): EstadoAyuda {
  return tipo === 'validacion'
    ? { ...estado, validacion: estado.validacion + 1 }
    : { ...estado, topePersonas: estado.topePersonas + 1 };
}

/** El cliente cerró el aviso: no se le vuelve a ofrecer en esta visita. */
export function descartarAyuda(estado: EstadoAyuda): EstadoAyuda {
  return { ...estado, descartada: true };
}

export function ofreceAyudaFlotante(estado: EstadoAyuda): boolean {
  return !estado.descartada
    && estado.validacion + estado.topePersonas >= TROPIEZOS_PARA_OFRECER_AYUDA;
}

/** Qué mensaje prellenar: el del tipo de tropiezo más frecuente (empate → validación). */
export function motivoDeAyuda(estado: EstadoAyuda): TipoTropiezo {
  return estado.topePersonas > estado.validacion ? 'tope-personas' : 'validacion';
}
