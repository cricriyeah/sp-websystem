import type {
  Aeropuerto, ComponenteOrdenInput, CrearOrdenInput, Moneda, PaqueteCatalogo, ReservaInput, TipoTraslado, Zona,
} from './api';
import type { SeleccionPersonalizacion } from './personalizaciones';

export type DatosContacto = { fullName: string; phone: string; email: string };

export type DetalleTraslado = {
  tipo: TipoTraslado;
  modo: 'catalogo' | 'personalizada';
  puntoEncuentroId: number | null;
  direccion: string;
  zonaLibre: Zona | '';
  fechaRegreso: string | null;
  /** Solo traslado fijo de paquete con hospedaje; '' hasta que la clienta lo elige. */
  aeropuerto: Aeropuerto | '';
};

export type ComponentePedido = {
  personas: number;
  extras: SeleccionPersonalizacion[];
  traslado?: DetalleTraslado;
};

type ZonaDePunto = (puntoId: number | null) => Zona | '';

/**
 * Misma regla que `DetalleTransporte.zona_efectiva()` del backend: la zona solo importa en
 * `redondo_actividad` (hotel del catálogo, o la zona elegida si es dirección libre); en los
 * tipos de aeropuerto las tarifas no llevan zona, aunque el hotel tenga una.
 */
export function zonaEfectivaDeTraslado(t: DetalleTraslado, zonaDePunto: ZonaDePunto): Zona | '' {
  if (t.tipo !== 'redondo_actividad') return '';
  return t.modo === 'catalogo' ? zonaDePunto(t.puntoEncuentroId) : t.zonaLibre;
}

type ArgsComunes = {
  checkoutId: string;
  paquete: PaqueteCatalogo;
  componentes: Record<string, ComponentePedido>;
  inicio: string;
  hora: string;
  moneda: Moneda;
  contacto: DatosContacto;
  ref?: string;
  /** Zona de un punto de encuentro del catálogo de traslados, o '' si no aplica. */
  zonaDePunto: ZonaDePunto;
};

/** Personas del componente operativo principal: el primer `por_recurso_dia`; si no hay, el primero. */
export function personasPrincipales(paquete: PaqueteCatalogo, componentes: Record<string, ComponentePedido>): number {
  const ordenados = [...paquete.servicios_asociados].sort((a, b) => a.orden - b.orden);
  const principal = ordenados.find((c) => c.servicio.estrategia_cupo === 'por_recurso_dia') ?? ordenados[0];
  return componentes[principal.servicio.slug]?.personas ?? 1;
}

export function armarPayloadOrden(args: ArgsComunes): CrearOrdenInput {
  const { paquete, componentes, contacto } = args;
  const tieneHospedaje = paquete.noches !== null && paquete.noches !== undefined;
  const ordenados = [...paquete.servicios_asociados].sort((a, b) => a.orden - b.orden);
  const principal = ordenados.find((c) => c.servicio.estrategia_cupo === 'por_recurso_dia') ?? ordenados[0];
  const nombre = contacto.fullName.trim();

  const filas: ComponenteOrdenInput[] = paquete.servicios_asociados.map((c) => {
    const actual = componentes[c.servicio.slug];
    const fila: ComponenteOrdenInput = {
      servicio: c.servicio.slug,
      ...(paquete.pide_hora !== false && c.servicio_id === principal?.servicio_id ? { hora: args.hora } : {}),
      numero_personas: actual.personas,
      personalizaciones: actual.extras,
    };
    if (c.servicio.tipo_servicio === 'transporte' && actual.traslado) {
      const t = actual.traslado;
      fila.tipo_traslado = t.tipo;
      fila.zona = zonaEfectivaDeTraslado(t, args.zonaDePunto);
      if (t.modo === 'catalogo') fila.punto_encuentro = t.puntoEncuentroId;
      else fila.direccion_personalizada = t.direccion.trim();
      if (t.tipo === 'redondo_aeropuerto' && !tieneHospedaje) fila.fecha_regreso = t.fechaRegreso;
    }
    return fila;
  });

  return {
    checkout_id: args.checkoutId,
    paquete: paquete.slug,
    deslinde_aceptado: true,
    deslinde_nombre: nombre,
    nombre_cliente: nombre,
    telefono_cliente: contacto.phone.trim(),
    correo_cliente: contacto.email.trim(),
    moneda: args.moneda,
    ref: args.ref,
    fecha: args.inicio,
    ...(paquete.pide_hora === false ? {} : { hora: args.hora }),
    componentes: filas,
  };
}

export function armarPayloadReserva(args: ArgsComunes): ReservaInput {
  const { paquete, componentes, contacto } = args;
  const nombre = contacto.fullName.trim();
  const personasPorServicio: Record<string, number> = {};
  const personalizaciones: ReservaInput['personalizaciones'] = [];
  let aeropuerto: Aeropuerto | '' = '';
  for (const c of paquete.servicios_asociados) {
    const actual = componentes[c.servicio.slug];
    if (c.servicio.tipo_servicio === 'transporte' && actual.traslado?.aeropuerto) aeropuerto = actual.traslado.aeropuerto;
    personasPorServicio[String(c.servicio_id)] = actual.personas;
    personalizaciones.push(...actual.extras.map((x) => ({ id: x.id, cantidad: x.cantidad, respuesta: x.respuesta })));
  }
  return {
    checkout_id: args.checkoutId,
    fecha: args.inicio,
    ...(paquete.pide_hora === false ? {} : { hora: args.hora }),
    numero_personas: personasPrincipales(paquete, componentes),
    personas_por_servicio: personasPorServicio,
    nombre_cliente: nombre,
    telefono_cliente: contacto.phone.trim(),
    correo_cliente: contacto.email.trim(),
    moneda: args.moneda,
    deslinde_aceptado: true,
    deslinde_nombre: nombre,
    ref: args.ref,
    paquete: paquete.slug,
    ...(aeropuerto ? { aeropuerto } : {}),
    personalizaciones,
  };
}
