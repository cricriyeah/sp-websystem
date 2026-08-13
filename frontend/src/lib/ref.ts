/**
 * Atribucion de ventas: quien vendio el viaje.
 *
 * La vendedora le pasa a su cliente un link con su codigo (`?ref=maria`). El
 * codigo se guarda en el navegador y viaja despues con la reserva, para que en
 * el backoffice la venta aparezca a su nombre sin que ella tenga que marcarla
 * (ver `Vendedora` en backend/apps/bookings/models.py).
 *
 * Se guarda al entrar al sitio y no solo en el checkout porque el link puede
 * caer en cualquier pagina: de la portada a `/reservar` el parametro se pierde,
 * el cliente puede irse a ver la flota y volver, o cerrar y comprar otro dia.
 */
const CLAVE_REF = 'salysol:ref';

/**
 * Cuanto vale la atribucion. Pasado ese plazo, una compra ya no cuenta como
 * venta de quien mando el link hace meses. 30 dias es lo habitual y da margen
 * de sobra para un viaje que se planea con anticipacion.
 */
const DIAS_DE_VIGENCIA = 30;

const MS_POR_DIA = 24 * 60 * 60 * 1000;

type RefGuardado = { codigo: string; guardadoEn: number };

/** Mismo formato que `Vendedora.codigo` (SlugField) en el backend. */
const FORMATO_CODIGO = /^[-\w]{1,30}$/;

/**
 * Guarda el `?ref=` de la URL actual, si trae uno valido.
 *
 * Un ref nuevo pisa al anterior: si el cliente entra hoy por el link de alguien
 * mas, la venta es de quien lo trajo esta vez.
 */
export function capturarRef(search: string) {
  const codigo = new URLSearchParams(search).get('ref');
  if (!codigo || !FORMATO_CODIGO.test(codigo)) return;

  try {
    const dato: RefGuardado = { codigo, guardadoEn: Date.now() };
    window.localStorage.setItem(CLAVE_REF, JSON.stringify(dato));
  } catch {
    // Modo privado o almacenamiento lleno. La venta queda sin atribuir y la
    // vendedora la marca a mano; no es motivo para romper la navegacion.
  }
}

/** El codigo vigente, o `undefined`. El backend ignora los que no resuelven. */
export function leerRef(): string | undefined {
  try {
    const crudo = window.localStorage.getItem(CLAVE_REF);
    if (!crudo) return undefined;

    const { codigo, guardadoEn }: RefGuardado = JSON.parse(crudo);
    if (Date.now() - guardadoEn > DIAS_DE_VIGENCIA * MS_POR_DIA) {
      window.localStorage.removeItem(CLAVE_REF);
      return undefined;
    }
    return codigo;
  } catch {
    return undefined;
  }
}
