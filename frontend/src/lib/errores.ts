import { ApiError } from '@/lib/api';

/**
 * Traduce un fallo tecnico a algo que el cliente pueda usar.
 *
 * Un mensaje de error tiene tres partes y hasta ahora solo teniamos la primera:
 *
 * 1. **Que paso** — en sus terminos, no en los del servidor.
 * 2. **Que hacer** — la accion concreta que lo saca del atolladero.
 * 3. **La salida de emergencia** — hablarle a una persona.
 *
 * La tercera es la que mas vale aqui y no se estaba usando. Este negocio tiene
 * un WhatsApp atendido por la vendedora: un canal humano dentro de un mensaje de
 * fallo convierte una venta perdida en una conversacion. Sin el, un error de red
 * en el wifi de un hotel es una venta que se va sin dejar rastro.
 */

export type ClaseDeFallo =
  /** No hay red, o el backend no contesta. Muy comun: turistas en wifi de hotel. */
  | 'conexion'
  /** El servidor contesto que algo no se puede todavia (Stripe sin configurar, tarifa ausente). */
  | 'no_disponible'
  /** Demasiadas peticiones desde esta IP. */
  | 'demasiados_intentos'
  /** El dia se lleno mientras el cliente llenaba el formulario. */
  | 'sin_cupo'
  /** Cualquier otra cosa. */
  | 'desconocido';

/**
 * De que tipo es este fallo.
 *
 * Un `ApiError` sin status util o un `TypeError` de `fetch` son lo mismo para el
 * cliente: no llego. Se agrupan a proposito — distinguirlos solo serviria para
 * darle un mensaje mas preciso sobre algo que no puede arreglar.
 */
export function clasificar(error: unknown): ClaseDeFallo {
  if (!(error instanceof ApiError)) return 'conexion';

  if (error.status === 429) return 'demasiados_intentos';
  if (error.status === 503) return 'no_disponible';
  if (error.status === 409) return 'sin_cupo';
  // 0 lo pone el cliente cuando el fetch ni siquiera llego a contestar.
  if (error.status === 0 || error.status >= 500) return 'conexion';
  return 'desconocido';
}

/** Textos del diccionario que necesita `mensajeDeFallo`. */
export type TextosDeError = Record<ClaseDeFallo, string>;

export function mensajeDeFallo(error: unknown, textos: TextosDeError) {
  return textos[clasificar(error)];
}

/**
 * El mensaje que se le manda a la vendedora cuando el cliente usa la salida de
 * emergencia.
 *
 * Lleva ya la fecha, la hora y el numero de personas: ella abre el chat sabiendo
 * que queria reservar el cliente, y el cliente no tiene que redactar nada estando
 * ya frustrado. Nunca incluye el detalle tecnico del error — a nadie le sirve
 * pegarle un 502 a una persona.
 */
export function mensajeDeAyuda(
  plantilla: string,
  datos: { fecha: string; hora: string; personas: number },
) {
  return plantilla
    .replace('{date}', datos.fecha)
    .replace('{time}', datos.hora)
    .replace('{people}', String(datos.personas));
}
