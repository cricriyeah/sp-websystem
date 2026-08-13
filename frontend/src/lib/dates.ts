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

export const MAX_PEOPLE = 6;
export const MIN_PEOPLE = 1;
