// Qué control de fecha pide cada cosa que se reserva. Sin React: el calendario (`ui/calendario`)
// y cada ruta lo leen de aquí para no decidirlo cada uno por su lado.
import type { TipoTraslado } from './api';

export type ControlFecha =
  /** Un día: pesca, paseo, tour, bajo demanda, traslado de un tramo, paquete sin hospedaje. */
  | 'fecha_unica'
  /** Hospedaje `por_noche` suelto: el cliente elige llegada y salida. */
  | 'rango_llegada_salida'
  /** Paquete con noches fijas: se elige la llegada y la salida sale de las noches. */
  | 'rango_fijo_paquete'
  /** Traslado redondo con aeropuerto: ida y regreso. */
  | 'ida_y_regreso';

export type EntradaControl =
  | { tipo: 'servicio'; estrategia_cupo: string; pide_hora: boolean }
  /** `noches`: las del hospedaje del paquete (`nochesDelPaquete`), o null si no lleva. */
  | { tipo: 'paquete'; noches: number | null; pide_hora: boolean }
  | { tipo: 'traslado'; tipoTraslado: TipoTraslado };

export function controlDeFecha(entrada: EntradaControl): { control: ControlFecha; pideHora: boolean } {
  switch (entrada.tipo) {
    case 'servicio':
      return {
        control: entrada.estrategia_cupo === 'por_noche' ? 'rango_llegada_salida' : 'fecha_unica',
        pideHora: entrada.pide_hora,
      };
    case 'paquete':
      return { control: entrada.noches ? 'rango_fijo_paquete' : 'fecha_unica', pideHora: entrada.pide_hora };
    case 'traslado':
      // Todo traslado pide hora de recogida.
      return { control: entrada.tipoTraslado === 'redondo_aeropuerto' ? 'ida_y_regreso' : 'fecha_unica', pideHora: true };
  }
}

/** En los rangos el primer toque es vista previa y el segundo confirma; en una fecha, un toque elige. */
export function pideDosToques(control: ControlFecha): boolean {
  return control !== 'fecha_unica';
}
