// El color de una salida dice qué tipo de actividad es (F10): azul = mar, coral = traslados, verde =
// estancia. Nunca es botón ni estado. Módulo puro, sin imports: lo prueba el runner.

export type ColorActividad = 'mar' | 'traslado' | 'estancia';

type ConTipo = { tipo_servicio: string };

export function colorDeServicio(servicio: ConTipo): ColorActividad {
  if (servicio.tipo_servicio === 'transporte') return 'traslado';
  if (servicio.tipo_servicio === 'hospedaje') return 'estancia';
  return 'mar';
}

/**
 * Un paquete con hospedaje es de estancia; sin él, de mar si incluye algo de mar; solo traslados,
 * de traslado. Un paquete vacío cae en mar.
 */
export function colorDePaquete(paquete: { servicios_asociados: { servicio: ConTipo }[] }): ColorActividad {
  const colores = new Set(paquete.servicios_asociados.map((c) => colorDeServicio(c.servicio)));
  if (colores.has('estancia')) return 'estancia';
  if (colores.has('mar') || colores.size === 0) return 'mar';
  return 'traslado';
}
