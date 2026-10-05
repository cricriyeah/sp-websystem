import { fromLocalISODate, toLocalISODate } from './dates';

const DIA_MS = 24 * 60 * 60 * 1000;

function sumarDias(iso: string, dias: number): string {
  const fecha = fromLocalISODate(iso);
  fecha.setDate(fecha.getDate() + dias);
  return toLocalISODate(fecha);
}

/** Días enteros entre dos fechas ISO; redondea para no tropezar con el cambio de horario. */
function diasEntre(desde: string, hasta: string): number {
  return Math.round((fromLocalISODate(hasta).getTime() - fromLocalISODate(desde).getTime()) / DIA_MS);
}

/**
 * Ventana de 7 días que arranca en el primer día reservable y avanza de 7 en 7
 * (no por semana de calendario): así nunca hay celdas pasadas que no se pueden
 * tocar al principio de la tira. Cada celda lleva su día de la semana, de modo
 * que no hace falta que la ventana empiece en lunes.
 */
export function semanaVisible(seleccionado: string | null, minDate: string) {
  const seleccionVigente = seleccionado && seleccionado >= minDate ? seleccionado : null;
  const ventanas = seleccionVigente ? Math.floor(diasEntre(minDate, seleccionVigente) / 7) : 0;
  const inicio = sumarDias(minDate, ventanas * 7);
  const dias = Array.from({ length: 7 }, (_, indice) => sumarDias(inicio, indice));
  return { inicio, dias, seleccionado: seleccionVigente };
}

export function puedeRetroceder(inicio: string, minDate: string) {
  return inicio > minDate;
}
