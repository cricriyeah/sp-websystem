import type { PaqueteCatalogo, ServicioCatalogo } from './api';
import { generarHorasVentana } from './dates';
import { servicioPrincipalPaquete } from './pedido-paquete';

/**
 * Las horas que se le ofrecen a la clienta para un servicio: salen del rango (apertura a cierre) y del
 * paso que la empresa dejó en el servicio, nunca de una lista fija. Un servicio que no pide hora no
 * ofrece ninguna, y sin rango no se inventa uno.
 */
export function horasDeServicio(
  servicio: Pick<ServicioCatalogo, 'pide_hora' | 'hora_apertura' | 'hora_cierre' | 'paso_hora_minutos'>,
): string[] {
  if (!servicio.pide_hora) return [];
  return generarHorasVentana(servicio.hora_apertura, servicio.hora_cierre, servicio.paso_hora_minutos);
}

/** Un paquete usa las horas de su actividad principal, y solo si el paquete pide hora. */
export function horasDePaquete(
  paquete: Pick<PaqueteCatalogo, 'pide_hora' | 'servicios_asociados'>,
): string[] {
  if (!paquete.pide_hora) return [];
  const principal = servicioPrincipalPaquete(paquete as PaqueteCatalogo);
  return principal ? horasDeServicio(principal.servicio) : [];
}
