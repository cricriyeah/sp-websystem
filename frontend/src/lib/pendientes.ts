const CLAVE = 'salysol:pendientes:v1';
const VIGENCIA_MS = 7 * 24 * 60 * 60 * 1000;
const TOPE = 3;

export type Pendiente = {
  tipo: 'reserva' | 'orden';
  checkoutId: string;
  ordenId?: number;
  sedeSlug?: string;
  empresaSlug: string;
  productoSlug: string;
  productoNombre: string;
  ruta: string;
  actualizadoEn: string;
  tieneDineroRetenido?: boolean;
};

function esPendiente(x: unknown): x is Pendiente {
  if (typeof x !== 'object' || x === null) return false;
  const p = x as Record<string, unknown>;
  return (p.tipo === 'reserva' || p.tipo === 'orden')
    && typeof p.checkoutId === 'string' && p.checkoutId.length > 0
    && typeof p.empresaSlug === 'string' && p.empresaSlug.length > 0
    && typeof p.productoSlug === 'string' && p.productoSlug.length > 0
    && typeof p.productoNombre === 'string'
    && typeof p.ruta === 'string' && p.ruta.length > 0
    && typeof p.actualizadoEn === 'string'
    && (p.ordenId === undefined || (typeof p.ordenId === 'number' && Number.isFinite(p.ordenId)))
    && (p.sedeSlug === undefined || typeof p.sedeSlug === 'string')
    && (p.tieneDineroRetenido === undefined || typeof p.tieneDineroRetenido === 'boolean');
}

function vigente(p: Pendiente): boolean {
  const fecha = Date.parse(p.actualizadoEn);
  const edad = Date.now() - fecha;
  return Number.isFinite(fecha) && edad >= 0 && edad < VIGENCIA_MS;
}

function leer(): Pendiente[] {
  try {
    const datos: unknown = JSON.parse(localStorage.getItem(CLAVE) ?? '[]');
    return Array.isArray(datos) ? datos.filter(esPendiente).filter(vigente) : [];
  } catch {
    return [];
  }
}

function escribir(lista: Pendiente[]): void {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(lista));
  } catch {
    // El checkout sigue funcionando si localStorage está bloqueado o lleno.
  }
}

export function listarPendientes(): Pendiente[] {
  return leer().sort((a, b) => Date.parse(b.actualizadoEn) - Date.parse(a.actualizadoEn));
}

export function guardarPendiente(p: Pendiente): void {
  if (!esPendiente(p) || !vigente(p)) return;
  const lista = [p, ...leer().filter((x) => x.checkoutId !== p.checkoutId)]
    .sort((a, b) => Date.parse(b.actualizadoEn) - Date.parse(a.actualizadoEn));
  if (lista.length > TOPE) {
    const descartable = [...lista].reverse().find((x) => !x.tieneDineroRetenido);
    // Conserva un cuarto pendiente si los tres anteriores tienen dinero retenido.
    if (descartable && !(descartable.checkoutId === p.checkoutId
      && lista.filter((x) => x.tieneDineroRetenido).length >= TOPE)) {
      lista.splice(lista.indexOf(descartable), 1);
    }
  }
  escribir(lista);
}

export function borrarPendiente(checkoutId: string): void {
  escribir(leer().filter((p) => p.checkoutId !== checkoutId));
}
