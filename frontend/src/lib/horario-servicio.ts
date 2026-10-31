import type { SedeContenido } from '@/content/sedes-tipos';
import type { PaqueteCatalogo, ServicioCatalogo } from './api';
import { formatHour, generarHorasVentana } from './dates';
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

/**
 * La ventana de salida como la dicen los textos del sitio: `hora` es la apertura completa («6:00 am»);
 * `desde` y `hasta` son los dos extremos de un rango, y `desde` pierde el «am» cuando los dos lo comparten
 * («6:00» a «7:00 am»). `null` sin rango: no se inventa uno.
 */
export type VentanaSalida = { hora: string; desde: string; hasta: string };

export function ventanaDeSalida(apertura?: string | null, cierre?: string | null): VentanaSalida | null {
  if (!apertura || !cierre) return null;
  const hora = formatHour(apertura);
  const hasta = formatHour(cierre);
  return { hora, desde: hora.slice(-2) === hasta.slice(-2) ? hora.slice(0, -3) : hora, hasta };
}

/**
 * Pone la ventana en los textos que la mencionan con `{hora}`, `{desde}` y `{hasta}`, en un texto suelto o
 * en todo un objeto de contenido. Así la hora vive solo en el backoffice y ningún texto la repite a mano.
 */
export function conVentana<T>(valor: T, ventana: VentanaSalida): T {
  const rellenar = (v: unknown): unknown => {
    if (typeof v === 'string') return v.replaceAll('{hora}', ventana.hora).replaceAll('{desde}', ventana.desde).replaceAll('{hasta}', ventana.hasta);
    if (Array.isArray(v)) return v.map(rellenar);
    if (v !== null && typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype) {
      return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, rellenar(x)]));
    }
    return v;
  };
  return rellenar(valor) as T;
}

/**
 * La sede con la ventana de su servicio destacado tal como está en el backoffice, en el horario del negocio
 * y en cada texto que la menciona. Si la API no respondió, se queda la que la sede trae escrita.
 */
export function sedeConVentana(sede: SedeContenido, servicios: ServicioCatalogo[] | null): SedeContenido {
  if (!sede.negocio) return sede;
  const destacada = sede.destacadas.find((d) => d.tipo === 'servicio');
  const servicio = destacada && servicios?.find((s) => s.slug === destacada.slug && (!destacada.empresaSlug || s.empresa_slug === destacada.empresaSlug));
  const negocio = servicio?.pide_hora && servicio.hora_apertura && servicio.hora_cierre
    ? { ...sede.negocio, horarioApertura: servicio.hora_apertura.slice(0, 5), horarioCierre: servicio.hora_cierre.slice(0, 5) }
    : sede.negocio;
  const ventana = ventanaDeSalida(negocio.horarioApertura, negocio.horarioCierre);
  return ventana ? conVentana({ ...sede, negocio }, ventana) : { ...sede, negocio };
}

/** «Salida entre {desde} y {hasta}» con la primera y la última hora que de verdad se ofrecen; sin horas, nada. */
export function ayudaDeHora(texto: string, horas: string[]): string | undefined {
  const ventana = ventanaDeSalida(horas[0], horas.at(-1));
  return ventana ? conVentana(texto, ventana) : undefined;
}
