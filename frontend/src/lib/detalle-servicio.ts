/**
 * Piezas puras del detalle de un servicio (pedido del dueño, 2026-11-16): las condiciones que van pegadas al precio,
 * el enlace al mapa del punto de salida y las reglas del viaje en etiquetas. Sin `server-only`: las prueba
 * `tests/detalle-servicio.test.cjs`.
 */

/** Qué clase de compra es, para decir su plazo de cambio (el mismo de `plantilla.plazo_de` en el backend). */
export type ClaseDeCompra = 'mar' | 'paquete-hotel' | 'paquete' | 'traslado' | 'otro';

type TextosCondiciones = {
  confirmas: string;
  clima: string;
  fecha48: string;
  fecha30: string;
  fecha24: string;
};

/**
 * Los renglones de «Reserva con tranquilidad» del bloque de compra. Se confirma al pagar siempre; el mal clima solo
 * cuenta donde se sale al mar; el plazo de cambio es el de lo que se compra (48 h un día de mar, 30 días un paquete
 * con hotel, 24 h un traslado). Un hospedaje suelto no dice plazo: no hay regla escrita para él.
 */
export function condicionesDeCompra(clase: ClaseDeCompra, alMar: boolean, textos: TextosCondiciones): string[] {
  const fecha = { mar: textos.fecha48, 'paquete-hotel': textos.fecha30, paquete: textos.fecha48, traslado: textos.fecha24, otro: null }[clase];
  return [textos.confirmas, ...(alMar ? [textos.clima] : []), ...(fecha ? [fecha] : [])];
}

/** Búsqueda en Google Maps del punto de salida con su lugar («Marina La Costa, La Paz, Baja California Sur»). */
export function enlaceAlMapa(punto: string, lugar?: string): string | null {
  const texto = punto.trim();
  if (!texto) return null;
  const consulta = lugar && !texto.toLowerCase().includes(lugar.toLowerCase()) ? `${texto}, ${lugar}, Baja California Sur` : texto;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(consulta)}`;
}

/** Las reglas confirmadas de un servicio; la que falta no se dice. */
export type ReglasServicio = {
  /** `true` = te quedas con tu pesca; `false` = captura y liberación. */
  quedasPesca?: boolean;
  /** Solo `true` se dice (te la limpian en el muelle). */
  limpieza?: boolean;
  /** Solo `true` se dice (niños bienvenidos). */
  ninos?: boolean;
  /** `true` = te recogen en tu hotel; `false` = llegas por tu cuenta al muelle. */
  recogida?: boolean;
};

type TextosReglas = { quedasPesca: string; liberacion: string; limpieza: string; ninos: string; recogida: string; llegas: string };

export function etiquetasDeReglas(reglas: ReglasServicio, textos: TextosReglas): string[] {
  return [
    ...(reglas.quedasPesca === undefined ? [] : [reglas.quedasPesca ? textos.quedasPesca : textos.liberacion]),
    ...(reglas.limpieza ? [textos.limpieza] : []),
    ...(reglas.ninos ? [textos.ninos] : []),
    ...(reglas.recogida === undefined ? [] : [reglas.recogida ? textos.recogida : textos.llegas]),
  ];
}
