// Borrador de una reserva a medias, solo en la pestaña (sessionStorage): sobrevive a
// recargar y a cambiar de idioma, que remonta el árbol, y desaparece al cerrar la
// pestaña o al confirmar el pago. El deslinde NO se guarda: se acepta de nuevo siempre.

const VERSION = 1;
const VIGENCIA_MS = 4 * 60 * 60 * 1000;
const PREFIJO = 'salysol:borrador:';

type Sobre = { version: number; guardadoEn: number; datos: unknown };

/** Clave por ruta y producto, p. ej. `salysol:borrador:reservar:pesca-deportiva`. */
export function claveBorrador(ruta: 'reservar' | 'paquete' | 'traslados', producto: string): string {
  return `${PREFIJO}${ruta}:${producto}`;
}

function almacen(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    // En modo privado el solo acceso a sessionStorage puede lanzar.
    return null;
  }
}

export function guardarBorrador(clave: string, datos: unknown, ahora: number = Date.now()): void {
  try {
    const sobre: Sobre = { version: VERSION, guardadoEn: ahora, datos };
    almacen()?.setItem(clave, JSON.stringify(sobre));
  } catch {
    // El checkout sigue funcionando sin borrador.
  }
}

/** Lo guardado, o `null` si no hay, está roto, es de otra versión o ya venció. */
export function leerBorrador<T = unknown>(clave: string, ahora: number = Date.now()): T | null {
  try {
    const crudo = almacen()?.getItem(clave);
    if (!crudo) return null;
    const sobre = JSON.parse(crudo) as Partial<Sobre> | null;
    if (!sobre || typeof sobre !== 'object' || sobre.version !== VERSION) return null;
    if (typeof sobre.guardadoEn !== 'number' || ahora < sobre.guardadoEn || ahora - sobre.guardadoEn >= VIGENCIA_MS) return null;
    if (sobre.datos === undefined || sobre.datos === null) return null;
    return sobre.datos as T;
  } catch {
    return null;
  }
}

export function borrarBorrador(clave: string): void {
  try {
    almacen()?.removeItem(clave);
  } catch {
    // Nada que borrar si el almacenamiento no está disponible.
  }
}
