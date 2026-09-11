import type { Moneda, PaqueteCatalogo } from './api';

export type PersonalizacionSeleccionada = {
  id: number;
  cantidad?: number;
};

export type CalculoPrecioPaquete = {
  precioAncla: number;
  totalPersonalizaciones: number;
  precioFinal: number;
  moneda: Moneda;
  serviciosActivosCount: number;
};

/**
 * Calcula de forma reactiva en cliente el precio del paquete.
 *
 * Fórmula:
 *     paquete.precio_en(moneda)                                              # el ancla
 *   + Σ  sp.precio_en(moneda) de cada ServicioPersonalizacion (obligatorio o preseleccionado)
 *        de los servicios componentes, con activo=True
 *   + Σ  sp.precio_en(moneda) de las ServicioPersonalizacion OPCIONALES que el cliente marcó
 *
 * Cada personalización que cobrar_por_persona se multiplica por personas.
 * Piso 0.
 */
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  moneda?: Moneda,
): CalculoPrecioPaquete;
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  personalizacionesOpcionales?: PersonalizacionSeleccionada[],
  personas?: number,
  moneda?: Moneda,
): CalculoPrecioPaquete;
export function calcularPrecioPaquete(
  paquete: PaqueteCatalogo,
  personalizacionesOMoneda?: PersonalizacionSeleccionada[] | Moneda,
  personasArg: number = 1,
  monedaArg: Moneda = 'MXN',
): CalculoPrecioPaquete {
  let personalizacionesOpcionales: PersonalizacionSeleccionada[] = [];
  let personas = personasArg;
  let moneda: Moneda = monedaArg;

  if (typeof personalizacionesOMoneda === 'string') {
    moneda = personalizacionesOMoneda;
    personalizacionesOpcionales = [];
    personas = 1;
  } else if (Array.isArray(personalizacionesOMoneda)) {
    personalizacionesOpcionales = personalizacionesOMoneda;
  }

  const anclaRaw =
    moneda === 'USD' && paquete.precio_ancla_usd
      ? paquete.precio_ancla_usd
      : paquete.precio_ancla;
  const precioAncla = parseFloat(anclaRaw) || 0;

  const opcionalesMap = new Map<number, number>();
  for (const p of personalizacionesOpcionales) {
    opcionalesMap.set(p.id, p.cantidad ?? 1);
  }

  let totalPersonalizaciones = 0;
  const serviciosActivosCount = paquete.servicios_asociados?.length ?? 0;

  for (const item of paquete.servicios_asociados || []) {
    for (const sp of item.servicio?.personalizaciones || []) {
      const esIncluida = sp.obligatorio || sp.preseleccionado;
      const esExtra = opcionalesMap.has(sp.id);

      if (!esIncluida && !esExtra) continue;

      const precioRaw =
        moneda === 'USD' && sp.precio_usd ? sp.precio_usd : sp.precio;
      const precioUnitario = parseFloat(precioRaw) || 0;

      const multPersonas = sp.cobrar_por_persona ? personas : 1;
      const cant = esExtra ? (opcionalesMap.get(sp.id) ?? 1) : 1;

      totalPersonalizaciones += precioUnitario * multPersonas * cant;
    }
  }

  const subtotal = precioAncla + totalPersonalizaciones;
  const precioFinal = Math.max(0, Math.round(subtotal * 100) / 100);

  return {
    precioAncla,
    totalPersonalizaciones: Math.round(totalPersonalizaciones * 100) / 100,
    precioFinal,
    moneda,
    serviciosActivosCount,
  };
}

/**
 * Un paquete es cruza-empresa cuando sus componentes pertenecen a mas de una
 * empresa (ej. pesca + traslado, cada uno de una empresa distinta de la
 * misma sede). Ese caso usa el checkout de orden (N pagos en secuencia), no
 * el checkout de reserva sencilla.
 */
export function esPaqueteCruzaEmpresa(paquete: PaqueteCatalogo): boolean {
  const empresas = new Set(paquete.servicios_asociados.map((s) => s.servicio.empresa_slug));
  return empresas.size > 1;
}

/**
 * Formatea un número como moneda (MXN o USD).
 */
export function formatearPrecio(monto: number, moneda: Moneda = 'MXN'): string {
  return new Intl.NumberFormat(moneda === 'USD' ? 'en-US' : 'es-MX', {
    style: 'currency',
    currency: moneda,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(monto);
}
