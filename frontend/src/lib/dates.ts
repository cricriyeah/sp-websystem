// Fecha ISO (YYYY-MM-DD) en hora LOCAL, no UTC. date.toISOString() convierte
// a UTC primero: en UTC-7 (America/Mazatlan) cualquier hora local despues de
// las 5pm ya cruzo la medianoche UTC y corre la fecha un dia extra.
export function toLocalISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// Primer dia reservable desde la web: mañana. Es una regla de la interfaz para
// no vender una salida de 5am del mismo dia; el documento de negocio no fija un
// minimo de anticipacion (lo que si fija son 48 horas para CAMBIAR de fecha, y
// eso lo valida el backend en Reserva.clean).
export function getMinBookableDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return toLocalISODate(date);
}

export const TOUR_HOURS = ['05:00', '05:15', '05:30', '05:45', '06:00', '06:15', '06:30', '06:45', '07:00'];

// 'HH:MM' de 24 horas a '6:30 am'. Las salidas son todas de madrugada, pero el
// periodo se calcula igual para no depender de eso.
export function formatHour(time: string) {
  const [h, m] = time.split(':').map(Number);
  const period = h >= 12 ? 'pm' : 'am';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, '0')} ${period}`;
}

// Fecha ISO a Date en hora local. Sin el sufijo, JS parsea 'YYYY-MM-DD' como UTC
// y en America/Mazatlan (UTC-7) cae en el dia anterior.
export function fromLocalISODate(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

/**
 * Tope de personas por viaje: la panga mas grande de la flota lleva 5.
 *
 * Tiene que coincidir con `MAX_PERSONAS` en backend/apps/bookings/models.py. El
 * servidor rechaza lo que se pase, asi que un valor mas alto aqui no vende de
 * mas — deja al cliente llenar todo el checkout para toparse con un 400 al
 * final, que es la peor forma de enterarse.
 */
export const MAX_PEOPLE = 5;
export const MIN_PEOPLE = 1;

/**
 * Lee dia/hora/personas de un parametro de la URL, validando cada uno por su
 * cuenta: uno mal formado no tira a los otros dos que si vinieron bien.
 * Devuelve `undefined` para lo que falte o no pase la validacion — nunca un
 * valor inventado. Quien llama decide el fallback: el checkout siempre
 * necesita uno (ahi no hay campo vacio posible), la portada no — un campo sin
 * responder se queda vacio a proposito.
 *
 * `get` es indireccion a proposito: `/[lang]/reservar` lee del `searchParams`
 * que le da el servidor, y la portada del `URLSearchParams` de
 * `window.location.search` en el cliente (ver el comentario largo en
 * `booking-state.tsx` sobre por que ahi no puede ser server-side).
 */
export function parseBookingQuery(
  get: (key: string) => string | undefined,
  minDate: string,
): { day?: string; time?: string; people?: number } {
  const dayParam = get('day');
  const day =
    dayParam && /^\d{4}-\d{2}-\d{2}$/.test(dayParam) && dayParam >= minDate ? dayParam : undefined;

  const timeParam = get('time');
  const time = timeParam && TOUR_HOURS.includes(timeParam) ? timeParam : undefined;

  const peopleParam = get('people');
  const peopleNum = peopleParam ? Number(peopleParam) : NaN;
  const people = Number.isInteger(peopleNum)
    ? Math.min(MAX_PEOPLE, Math.max(MIN_PEOPLE, peopleNum))
    : undefined;

  return { day, time, people };
}
