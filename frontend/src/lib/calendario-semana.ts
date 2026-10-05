import { fromLocalISODate, toLocalISODate } from './dates';

function inicioSemana(iso: string): string {
  const fecha = fromLocalISODate(iso);
  fecha.setDate(fecha.getDate() - (fecha.getDay() + 6) % 7);
  return toLocalISODate(fecha);
}

export function semanaVisible(seleccionado: string | null, minDate: string) {
  const seleccionVigente = seleccionado && seleccionado >= minDate ? seleccionado : null;
  const inicio = inicioSemana(seleccionVigente ?? minDate);
  const lunes = fromLocalISODate(inicio);
  const dias = Array.from({ length: 7 }, (_, indice) => {
    const fecha = new Date(lunes);
    fecha.setDate(fecha.getDate() + indice);
    return toLocalISODate(fecha);
  });
  return { inicio, dias, seleccionado: seleccionVigente };
}

export function puedeRetroceder(inicio: string, minDate: string) {
  return inicio > inicioSemana(minDate);
}
