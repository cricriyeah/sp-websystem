/**
 * Eventos de venta para la publicidad (plan de marketing, 2026-11-11): un solo punto que avisa al pixel de Meta
 * y a Google Analytics. Los dos se cargan solo con las cookies aceptadas (`pixel-meta.tsx`,
 * `google-analytics.tsx`); sin ellos estas funciones no hacen nada. Nunca lanzan: medir no puede romper una
 * compra.
 *
 * Eventos (nombres estándar de Meta; el de Google entre paréntesis):
 * - `ViewContent` (`view_item`): abrió la página de un servicio o paquete.
 * - `InitiateCheckout` (`begin_checkout`): llegó a pagar.
 * - `Purchase` (`purchase`): pagó. Con `eventID` = `reserva-<folio>` u `orden-<folio>`, el mismo que manda el
 *   servidor a la API de Conversiones, para que Meta no la cuente dos veces.
 * - `Contact` (`contact_whatsapp`): tocó un enlace de WhatsApp.
 */
export type EventoVenta = 'ViewContent' | 'InitiateCheckout' | 'Purchase' | 'Contact';

export type DatosEvento = {
  /** Slug del servicio o paquete. */
  id?: string;
  nombre?: string;
  valor?: number;
  moneda?: string;
  /** Para no contar dos veces la misma compra (navegador y servidor). */
  eventoId?: string;
};

const NOMBRE_GOOGLE: Record<EventoVenta, string> = {
  ViewContent: 'view_item',
  InitiateCheckout: 'begin_checkout',
  Purchase: 'purchase',
  Contact: 'contact_whatsapp',
};

type Fbq = (accion: string, evento: string, datos?: Record<string, unknown>, opciones?: Record<string, unknown>) => void;
type Gtag = (accion: string, evento: string, datos?: Record<string, unknown>) => void;

/** Parámetros de Meta para un evento; pura (la prueba `tests/medicion.test.cjs`). */
export function parametrosMeta(datos: DatosEvento): Record<string, unknown> {
  return {
    ...(datos.id ? { content_ids: [datos.id], content_type: 'product' } : {}),
    ...(datos.nombre ? { content_name: datos.nombre } : {}),
    ...(datos.valor !== undefined && Number.isFinite(datos.valor) ? { value: Number(datos.valor.toFixed(2)) } : {}),
    ...(datos.moneda ? { currency: datos.moneda } : {}),
  };
}

/** Parámetros de Google Analytics 4 para un evento; pura. */
export function parametrosGoogle(evento: EventoVenta, datos: DatosEvento): Record<string, unknown> {
  return {
    ...(datos.valor !== undefined && Number.isFinite(datos.valor) ? { value: Number(datos.valor.toFixed(2)) } : {}),
    ...(datos.moneda ? { currency: datos.moneda } : {}),
    ...(evento === 'Purchase' && datos.eventoId ? { transaction_id: datos.eventoId } : {}),
    ...(datos.id ? { items: [{ item_id: datos.id, ...(datos.nombre ? { item_name: datos.nombre } : {}) }] } : {}),
  };
}

export function medir(evento: EventoVenta, datos: DatosEvento = {}) {
  try {
    const ventana = window as unknown as { fbq?: Fbq; gtag?: Gtag };
    ventana.fbq?.('track', evento, parametrosMeta(datos), datos.eventoId ? { eventID: datos.eventoId } : undefined);
    ventana.gtag?.('event', NOMBRE_GOOGLE[evento], parametrosGoogle(evento, datos));
  } catch {
    // Un bloqueador o un script a medio cargar: la compra sigue.
  }
}

/**
 * La compra se mide una sola vez por folio aunque la confirmación se vuelva a pintar o el cliente recargue
 * la pestaña (`sessionStorage`). Devuelve si la midió.
 */
export function medirCompraUnaVez(datos: DatosEvento & { eventoId: string }): boolean {
  const clave = `salysol:compra-medida:${datos.eventoId}`;
  try {
    if (window.sessionStorage.getItem(clave)) return false;
    window.sessionStorage.setItem(clave, '1');
  } catch {
    // Sin almacenamiento se mide igual: es mejor un posible doble conteo (Meta lo une por eventID) que perderla.
  }
  medir('Purchase', datos);
  return true;
}

/** ¿Este enlace abre WhatsApp? */
export function esEnlaceWhatsapp(href: string): boolean {
  return /^https?:\/\/(wa\.me|api\.whatsapp\.com|(www\.)?whatsapp\.com\/send)/i.test(href);
}
