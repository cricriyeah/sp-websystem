/**
 * De dónde llegó el cliente (plan de marketing, 2026-11-11): el enlace por el que entró al sitio.
 *
 * Se guarda al entrar, en cualquier página, y viaja con la reserva igual que el `?ref=` de la vendedora
 * (`lib/ref.ts`): el anuncio puede llevar a la sede y la compra ocurrir tres clics o dos días después.
 * El backend limpia lo que llega (`backend/apps/bookings/atribucion.py`); aquí nada lanza.
 *
 * Regla: **gana el último enlace con parámetros** (un anuncio nuevo pisa al anterior). Una visita sin
 * parámetros no borra lo guardado; si no hay nada guardado y el cliente viene de otro sitio (Google sin
 * anuncio, TripAdvisor, Instagram), se guarda de qué sitio venía.
 */
const CLAVE = 'salysol:atribucion';
const DIAS_DE_VIGENCIA = 30;
const MS_POR_DIA = 24 * 60 * 60 * 1000;

export const PARAMETROS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid', 'gclid'] as const;

export type Atribucion = Partial<Record<(typeof PARAMETROS)[number] | 'referrer' | 'landing' | 'capturado_en' | 'fbp' | 'fbc', string>>;

type Guardada = { datos: Atribucion; guardadoEn: number };

/** Solo el dominio del sitio de origen, sin `www.`; vacío si es este mismo sitio o no se puede leer. */
export function dominioDeOrigen(referrer: string, hostPropio: string): string {
  try {
    const host = new URL(referrer).hostname.replace(/^www\./, '');
    return host && host !== hostPropio.replace(/^www\./, '') ? host : '';
  } catch {
    return '';
  }
}

/**
 * Qué guardar de esta visita, o `null` si no hay nada nuevo. Pura: la prueban `tests/atribucion.test.cjs`.
 * `hayGuardada` dice si ya hay una atribución vigente (una visita sin parámetros no la pisa).
 */
export function atribucionDeVisita(
  { search, referrer, hostPropio, ruta, ahora, hayGuardada }:
  { search: string; referrer: string; hostPropio: string; ruta: string; ahora: Date; hayGuardada: boolean },
): Atribucion | null {
  const query = new URLSearchParams(search);
  const datos: Atribucion = {};
  for (const clave of PARAMETROS) {
    const valor = query.get(clave)?.trim();
    if (valor) datos[clave] = valor.slice(0, 300);
  }
  const origen = dominioDeOrigen(referrer, hostPropio);
  const conParametros = Object.keys(datos).length > 0;
  if (!conParametros && (hayGuardada || !origen)) return null;
  if (origen) datos.referrer = origen;
  datos.landing = ruta.slice(0, 300);
  datos.capturado_en = ahora.toISOString();
  return datos;
}

function leerGuardada(): Atribucion | undefined {
  try {
    const crudo = window.localStorage.getItem(CLAVE);
    if (!crudo) return undefined;
    const { datos, guardadoEn }: Guardada = JSON.parse(crudo);
    if (Date.now() - guardadoEn > DIAS_DE_VIGENCIA * MS_POR_DIA) {
      window.localStorage.removeItem(CLAVE);
      return undefined;
    }
    return datos;
  } catch {
    return undefined;
  }
}

/** Guarda lo de esta visita si trae algo nuevo. Lo llama `RefCapture` en cada cambio de página. */
export function capturarAtribucion() {
  try {
    const datos = atribucionDeVisita({
      search: window.location.search,
      referrer: document.referrer,
      hostPropio: window.location.hostname,
      ruta: window.location.pathname,
      ahora: new Date(),
      hayGuardada: leerGuardada() !== undefined,
    });
    if (!datos) return;
    const guardada: Guardada = { datos, guardadoEn: Date.now() };
    window.localStorage.setItem(CLAVE, JSON.stringify(guardada));
  } catch {
    // Modo privado o almacenamiento lleno: la venta queda sin origen, no se rompe nada.
  }
}

/** Valor de una cookie del navegador, o ''. */
function cookie(nombre: string): string {
  try {
    const par = document.cookie.split('; ').find((c) => c.startsWith(`${nombre}=`));
    return par ? decodeURIComponent(par.slice(nombre.length + 1)) : '';
  } catch {
    return '';
  }
}

/**
 * Lo que viaja con la reserva: la atribución guardada y, si el pixel de Meta cargó (solo con las cookies
 * aceptadas), sus cookies `_fbp`/`_fbc`, que la API de Conversiones usa para unir la compra con el anuncio.
 * `undefined` si no hay nada.
 */
export function leerAtribucion(): Atribucion | undefined {
  const datos: Atribucion = { ...(leerGuardada() ?? {}) };
  const fbp = cookie('_fbp');
  const fbc = cookie('_fbc');
  if (fbp) datos.fbp = fbp;
  if (fbc) datos.fbc = fbc;
  return Object.keys(datos).length > 0 ? datos : undefined;
}
