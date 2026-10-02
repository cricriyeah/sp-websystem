import type { Moneda, PaqueteCatalogo, PaqueteServicioCatalogo, TipoTraslado, Zona } from './api';
import { totalPersonalizaciones, type SeleccionPersonalizacion } from './personalizaciones';
import { precioTarifa, resolverTarifa, type Tarifa } from './tarifa-transporte';

/**
 * Vista previa del reparto por empresa (el servidor lo recalcula: ver
 * backend/apps/payments/pricing.py::monto_por_empresa y CrearPagoOrdenView).
 * Regla: el traslado de otra empresa va a su tarifa; la líder absorbe el residuo
 * del precio del paquete; a cada empresa se le suman los extras de SUS servicios.
 */
export type SeleccionComponente = {
  personas: number;
  extras: SeleccionPersonalizacion[];
  traslado?: { tipo: TipoTraslado; zona: Zona | '' };
};

export type CargoEmpresa = { empresaSlug: string; monto: number; extras: number };
export type ResultadoPedido = { cargos: CargoEmpresa[]; total: number };

/** El mismo componente operativo que usa el payload para numero_personas. */
export function servicioPrincipalPaquete(paquete: PaqueteCatalogo): PaqueteServicioCatalogo | undefined {
  const ordenados = [...paquete.servicios_asociados].sort((a, b) => a.orden - b.orden);
  return ordenados.find((c) => c.servicio.estrategia_cupo === 'por_recurso_dia') ?? ordenados[0];
}

/**
 * Un paquete de una sola empresa con hospedaje trae el traslado ya definido: redondo con aeropuerto,
 * y el hotel es el del paquete. La clienta solo elige de que aeropuerto llega.
 */
export function trasladoFijoAeropuerto(paquete: Pick<PaqueteCatalogo, 'es_cruza_empresa' | 'noches'>): boolean {
  return !paquete.es_cruza_empresa && paquete.noches != null;
}

/** El grupo principal se limita por la capacidad de la actividad. */
export function maxPersonasPaquete(paquete: PaqueteCatalogo): number {
  return servicioPrincipalPaquete(paquete)?.personas_incluidas ?? 0;
}

const centavos = (n: number) => Math.round(n * 100);

function precioAncla(paquete: PaqueteCatalogo, moneda: Moneda): number | null {
  const crudo = moneda === 'USD' ? paquete.precio_ancla_usd : paquete.precio_ancla;
  if (crudo === null || crudo === undefined || crudo === '' || !Number.isFinite(Number(crudo))) return null;
  return Number(crudo);
}

export function calcularPedido(
  paquete: PaqueteCatalogo,
  selecciones: Record<string, SeleccionComponente>,
  moneda: Moneda,
  tarifasPorEmpresa: Record<string, Tarifa[]>,
): ResultadoPedido | null {
  const ancla = precioAncla(paquete, moneda);
  if (ancla === null) return null;

  const principal = paquete.precio_por_persona ? servicioPrincipalPaquete(paquete) : undefined;
  const personas = principal ? selecciones[principal.servicio.slug]?.personas : 1;
  if (paquete.precio_por_persona && (!principal || !Number.isInteger(personas) || personas < 1 ||
    paquete.servicios_asociados.some((c) => {
      const cantidad = selecciones[c.servicio.slug]?.personas;
      return !Number.isInteger(cantidad) || cantidad < 1 || cantidad > personas;
    }))) return null;
  const totalAncla = centavos(ancla) * personas;

  const lider = paquete.empresa_lider_slug;
  const extrasPorEmpresa = new Map<string, number>();
  const fijosPorEmpresa = new Map<string, number>();
  const orden: string[] = [];

  for (const componente of paquete.servicios_asociados) {
    const servicio = componente.servicio;
    const seleccion = selecciones[servicio.slug];
    if (!seleccion) return null;

    const totalExtras = totalPersonalizaciones(
      servicio.personalizaciones, seleccion.extras, seleccion.personas, moneda,
    );
    if (totalExtras === null) return null;

    const empresa = servicio.empresa_slug;
    if (!orden.includes(empresa)) orden.push(empresa);
    extrasPorEmpresa.set(empresa, (extrasPorEmpresa.get(empresa) ?? 0) + centavos(totalExtras));

    if (empresa !== lider) {
      // v1: lo único que puede ser de otra empresa es el traslado, y su parte es su tarifa.
      if (servicio.tipo_servicio !== 'transporte' || !seleccion.traslado) return null;
      const tarifa = resolverTarifa(
        tarifasPorEmpresa[empresa] ?? [], seleccion.traslado.tipo, seleccion.traslado.zona, seleccion.personas,
      );
      const precio = tarifa ? precioTarifa(tarifa, moneda) : null;
      if (precio === null) return null;
      fijosPorEmpresa.set(empresa, (fijosPorEmpresa.get(empresa) ?? 0) + centavos(precio));
    }
  }

  const fijos = [...fijosPorEmpresa.values()].reduce((suma, c) => suma + c, 0);
  const residuo = totalAncla - fijos;
  if (residuo < 0) return null;

  const cargos: CargoEmpresa[] = orden
    .sort((a, b) => Number(b === lider) - Number(a === lider))
    .map((empresa) => {
      const base = empresa === lider ? residuo : (fijosPorEmpresa.get(empresa) ?? 0);
      const extras = extrasPorEmpresa.get(empresa) ?? 0;
      return { empresaSlug: empresa, monto: (base + extras) / 100, extras: extras / 100 };
    });

  return { cargos, total: cargos.reduce((suma, c) => suma + centavos(c.monto), 0) / 100 };
}

/** USD solo se ofrece si el paquete y cada traslado incluido tienen precio en USD. */
export function usdDisponible(paquete: PaqueteCatalogo, tarifasPorEmpresa: Record<string, Tarifa[]>): boolean {
  if (precioAncla(paquete, 'USD') === null) return false;
  return paquete.servicios_asociados.every((componente) => {
    if (componente.servicio.tipo_servicio !== 'transporte') return true;
    const tarifas = tarifasPorEmpresa[componente.servicio.empresa_slug] ?? [];
    return tarifas.length > 0 && tarifas.every((t) => precioTarifa(t, 'USD') !== null);
  });
}

export function montoInicial(total: number, formaPago: 'completo' | 'anticipo', porcentaje: number): number {
  if (formaPago === 'completo') return total;
  return Math.round(centavos(total) * (porcentaje / 100)) / 100;
}
