import type { Moneda, PaqueteCatalogo, TipoTraslado, Zona } from './api';
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
  const residuo = centavos(ancla) - fijos;
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
