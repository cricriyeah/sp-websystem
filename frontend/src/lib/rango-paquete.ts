// El rango de fechas de un paquete con noches fijas, para pintarlo en el calendario. Solo vista
// previa: el servidor recalcula las fechas, y el cupo definitivo se valida al pagar.
import { sumarDias } from './calendario-paquete';

export type RangoPaquete = {
  llegada: string;
  salida: string;
  /** Las noches que se duermen (sin el día de salida); con 0 noches, el único día. */
  noches: string[];
  /** De la llegada a la salida, ambos incluidos: lo que el calendario pinta como banda. */
  dias: string[];
};

export function rangoDelPaquete(llegada: string, noches: number | null): RangoPaquete {
  const total = Math.max(0, noches ?? 0);
  const dias = Array.from({ length: total + 1 }, (_, i) => sumarDias(llegada, i));
  return {
    llegada,
    salida: dias[dias.length - 1],
    noches: total === 0 ? [llegada] : dias.slice(0, total),
    dias,
  };
}

/**
 * Las noches del rango que el cupo ya declara llenas (`getCupoRango`: cualquier motivo no nulo).
 * Sin datos de un día, no se marca: no se inventan «pocos lugares».
 */
export function diasSinCupoEnRango(
  rango: RangoPaquete,
  disponibilidad: Record<string, string | null | undefined>,
): string[] {
  return rango.noches.filter((dia) => Boolean(disponibilidad[dia]));
}
