// Fecha ISO (YYYY-MM-DD) en hora LOCAL, no UTC. date.toISOString() convierte
// a UTC primero: en UTC-7 (America/Mazatlan) cualquier hora local despues de
// las 5pm ya cruzo la medianoche UTC y corre la fecha un dia extra.
export function toLocalISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// Reserva requiere minimo 24 horas de anticipacion (no se puede reservar
// para el mismo dia), ver docs/contexto-negocio.md.
export function getMinBookableDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return toLocalISODate(date);
}

export const TOUR_HOURS = ['05:00', '05:15', '05:30', '05:45', '06:00', '06:15', '06:30', '06:45', '07:00'];

export const MAX_PEOPLE = 6;
export const MIN_PEOPLE = 1;
