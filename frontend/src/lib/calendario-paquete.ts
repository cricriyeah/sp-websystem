import { fromLocalISODate, toLocalISODate } from './dates';

/**
 * Espejo de backend/apps/fleet/calendario_paquete.py. Es solo vista previa: el
 * servidor recalcula todas las fechas y rechaza las que mande el cliente. El
 * vector de prueba compartido está en el spec §5/§7.
 */
export type ComponenteCalendario = {
  dia_estancia: number;
  estrategia_cupo: string;
  noches: number | null;
};

export function sumarDias(iso: string, dias: number): string {
  const fecha = fromLocalISODate(iso);
  fecha.setDate(fecha.getDate() + dias);
  return toLocalISODate(fecha);
}

export function nochesDelPaquete(componentes: ComponenteCalendario[]): number | null {
  return componentes.find((c) => c.estrategia_cupo === 'por_noche')?.noches ?? null;
}

export function fechaDeComponente(inicio: string, diaEstancia: number): string {
  return sumarDias(inicio, diaEstancia - 1);
}

export function fechaSalida(inicio: string, componentes: ComponenteCalendario[]): string | null {
  const noches = nochesDelPaquete(componentes);
  return noches ? sumarDias(inicio, noches) : null;
}
