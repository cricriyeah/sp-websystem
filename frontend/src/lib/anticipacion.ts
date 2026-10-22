// Anticipación mínima de la reserva web: un servicio con hora de salida exige HORAS_ANTICIPACION horas entre el
// momento de reservar y esa salida, contadas en la hora de la sede; lo que no tiene hora se reserva desde mañana.
// Espejo de `backend/apps/bookings/anticipacion.py`, que es quien la hace cumplir; aquí solo se dejan de ofrecer
// las fechas y horas que el servidor rechazaría. Sin React ni red.

/** Las horas de anticipación; el backend toma las suyas de `HORAS_MINIMAS_RESERVA` y deben coincidir. */
export const HORAS_ANTICIPACION = Number(process.env.NEXT_PUBLIC_HORAS_MINIMAS_RESERVA ?? 16);

/** Las tres sedes están en Baja California Sur (sin horario de verano). */
export const ZONA_SEDE = 'America/Mazatlan';

const partes = (instante: Date, zona: string) => {
  const trozos = new Intl.DateTimeFormat('en-CA', {
    timeZone: zona, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).formatToParts(instante);
  const valor = (tipo: string) => Number(trozos.find((t) => t.type === tipo)?.value);
  return { anio: valor('year'), mes: valor('month'), dia: valor('day'), hora: valor('hour'), minuto: valor('minute') };
};

const iso = (anio: number, mes: number, dia: number) =>
  `${String(anio).padStart(4, '0')}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;

/** El día de la sede ahora mismo, `YYYY-MM-DD`. */
export function hoyEnSede(ahora: Date = new Date(), zona: string = ZONA_SEDE): string {
  const p = partes(ahora, zona);
  return iso(p.anio, p.mes, p.dia);
}

/** Cuántos milisegundos se adelanta la hora de la zona al UTC en ese instante. */
const desfaseDeZona = (instante: Date, zona: string): number => {
  const p = partes(instante, zona);
  return Date.UTC(p.anio, p.mes - 1, p.dia, p.hora, p.minuto) - Math.floor(instante.getTime() / 60_000) * 60_000;
};

/** El instante en que ocurre `fecha` `hora` ('HH:MM') en la zona de la sede. */
export function instanteDeSalida(fecha: string, hora: string, zona: string = ZONA_SEDE): number {
  const [anio, mes, dia] = fecha.split('-').map(Number);
  const [h, m] = hora.split(':').map(Number);
  const comoUtc = Date.UTC(anio, mes - 1, dia, h, m);
  return comoUtc - desfaseDeZona(new Date(comoUtc), zona);
}

/** ¿`fecha` `hora` cumple la anticipación mínima? */
export function cumpleAnticipacion(
  fecha: string, hora: string, ahora: Date = new Date(), horas: number = HORAS_ANTICIPACION, zona: string = ZONA_SEDE,
): boolean {
  if (horas <= 0) return true;
  return instanteDeSalida(fecha, hora, zona) >= ahora.getTime() + horas * 3_600_000;
}

/** De las horas del servicio, las que ese día cumplen la anticipación. */
export function horasConAnticipacion(
  fecha: string, horas: string[], ahora: Date = new Date(), minimo: number = HORAS_ANTICIPACION, zona: string = ZONA_SEDE,
): string[] {
  return horas.filter((hora) => cumpleAnticipacion(fecha, hora, ahora, minimo, zona));
}

const sumarDias = (fecha: string, dias: number) => {
  const [anio, mes, dia] = fecha.split('-').map(Number);
  const d = new Date(Date.UTC(anio, mes - 1, dia + dias));
  return iso(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
};

/**
 * La primera fecha reservable. Sin horas (el servicio no pide hora): mañana, día de la sede. Con horas: la
 * primera en la que la última hora del servicio aún cumple la anticipación; las anteriores de ese día se ocultan
 * con `horasConAnticipacion`.
 */
export function fechaMinimaReservable(
  horas: string[] = [], ahora: Date = new Date(), minimo: number = HORAS_ANTICIPACION, zona: string = ZONA_SEDE,
): string {
  const hoy = hoyEnSede(ahora, zona);
  const manana = sumarDias(hoy, 1);
  if (horas.length === 0 || minimo <= 0) return manana;
  const ultima = horas[horas.length - 1];
  for (let dias = 0; dias <= 4; dias += 1) {
    const fecha = sumarDias(hoy, dias);
    if (cumpleAnticipacion(fecha, ultima, ahora, minimo, zona)) return fecha;
  }
  return sumarDias(hoy, 5);
}
