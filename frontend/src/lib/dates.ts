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


/**
 * Genera las horas seleccionables para una ventana horaria (apertura y cierre en 'HH:MM'),
 * con saltos de pasoMinutos (default 15). Sin rango no hay horas: la ventana es un dato de cada
 * servicio y no se inventa una por omisión.
 */
export function generarHorasVentana(
  apertura?: string | null,
  cierre?: string | null,
  pasoMinutos = 15
): string[] {
  if (!apertura || !cierre || pasoMinutos < 1) {
    return [];
  }
  const [hIni, mIni] = apertura.split(':').map(Number);
  const [hFin, mFin] = cierre.split(':').map(Number);
  const totalIni = hIni * 60 + mIni;
  const totalFin = hFin * 60 + mFin;
  if (totalIni > totalFin) return [];

  const horas: string[] = [];
  for (let m = totalIni; m <= totalFin; m += pasoMinutos) {
    const hh = String(Math.floor(m / 60)).padStart(2, '0');
    const mm = String(m % 60).padStart(2, '0');
    horas.push(`${hh}:${mm}`);
  }
  return horas;
}

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
 * Tope de personas por viaje: la panga mas grande de la flota lleva 5 (pesca default).
 * Otros servicios (e.g. transporte, hospedaje) configuran su propio tope vía `capacidad_maxima`.
 */
export const PESCA_MAX_PEOPLE = 5;
export const MAX_PEOPLE = PESCA_MAX_PEOPLE;
export const MIN_PEOPLE = 1;

/**
 * Retorna el tope de personas efectivo para un servicio o experiencia.
 */
export function getTopePersonas(capacidadMaxima?: number | null): number {
  return capacidadMaxima && capacidadMaxima > 0 ? capacidadMaxima : MAX_PEOPLE;
}

/**
 * Lee dia/hora/personas de un parametro de la URL, validando cada uno por su
 * cuenta: uno mal formado no tira a los otros dos que si vinieron bien.
 * Devuelve `undefined` para lo que falte o no pase la validacion — nunca un
 * valor inventado. Quien llama decide el fallback: el checkout siempre
 * necesita uno (ahi no hay campo vacio posible), la portada no — un campo sin
 * responder se queda vacio a proposito.
 *
 * La hora solo se valida de formato (HH:MM): si cabe en el rango del servicio lo decide cada
 * checkout con las horas de ese servicio, no una lista fija de aquí.
 * Acepta opciones para sobreescribir el rango de personas.
 */
export function parseBookingQuery(
  get: (key: string) => string | undefined,
  minDate: string,
  options?: {
    maxPeople?: number;
    minPeople?: number;
  }
): { day?: string; time?: string; people?: number } {
  const dayParam = get('day');
  const day =
    dayParam && /^\d{4}-\d{2}-\d{2}$/.test(dayParam) && dayParam >= minDate ? dayParam : undefined;

  const timeParam = get('time');
  const time = timeParam && /^([01]\d|2[0-3]):[0-5]\d$/.test(timeParam) ? timeParam : undefined;

  const max = options?.maxPeople ?? MAX_PEOPLE;
  const min = options?.minPeople ?? MIN_PEOPLE;
  const peopleParam = get('people');
  const peopleNum = peopleParam ? Number(peopleParam) : NaN;
  const people = Number.isInteger(peopleNum)
    ? Math.min(max, Math.max(min, peopleNum))
    : undefined;

  return { day, time, people };
}

