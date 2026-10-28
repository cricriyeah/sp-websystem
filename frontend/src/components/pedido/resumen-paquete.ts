import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { PaqueteCatalogo, PuntoEncuentro } from '@/lib/api';
import { formatHour } from '@/lib/dates';
import type { EstadoPedido } from '@/lib/pedido-estado';
import type { DetalleTraslado } from '@/lib/pedido-payload';
import { lineaDeTelefono } from '@/lib/telefono-campo';

type Entrada = {
  paquete: PaqueteCatalogo;
  inicio: string | null;
  hora: string;
  contacto: EstadoPedido['contacto'];
  personasPaquete: number;
  salida: string | null;
  noches: number | null;
  checkout: Dictionary['checkout'];
  traslados: Dictionary['traslados'];
  pedido: Dictionary['pedido'];
  puntosPorEmpresa: Record<string, PuntoEncuentro[]>;
  nombreEmpresa: (slug: string) => string;
  formatearFecha: (iso: string) => string;
  nombrePais: (iso: string) => string | undefined;
};

/**
 * Los textos que resumen el pedido del paquete (encabezado de la compra, el
 * renglón del viaje, las líneas de viaje y de contacto, y la línea del punto de
 * recogida). Derivación pura durante el render: no guarda ni lee estado.
 */
export function armarResumenPaquete({
  paquete, inicio, hora, contacto, personasPaquete, salida, noches, checkout, traslados, pedido, puntosPorEmpresa,
  nombreEmpresa, formatearFecha, nombrePais,
}: Entrada) {
  const empresas = [...new Set(paquete.servicios_asociados.map((c) => nombreEmpresa(c.servicio.empresa_slug)))];
  const detalleCompra = [
    paquete.sede,
    empresas.join(' + '),
    noches !== null ? checkout.purchaseNights.replace('{n}', String(noches)) : null,
  ].filter(Boolean).join(' · ');
  const lineasViaje = [
    inicio ? { etiqueta: checkout.summary.date, valor: formatearFecha(inicio) } : null,
    salida && noches !== null ? { etiqueta: checkout.summary.checkOut, valor: formatearFecha(salida) } : null,
    paquete.pide_hora && hora ? { etiqueta: checkout.summary.time, valor: formatHour(hora) } : null,
    // Una actividad con salidas en varios días: informativo («Actividad: días 2 a 5»).
    ...paquete.servicios_asociados.map((c) => (c.salidas > 1
      ? {
          etiqueta: c.servicio.nombre,
          valor: pedido.salidasDias
            .replace('{desde}', String(c.dia_estancia))
            .replace('{hasta}', String(c.dia_estancia + c.salidas - 1)),
        }
      : null)),
    paquete.precio_depende_de_personas
      ? { etiqueta: checkout.summary.people, valor: String(personasPaquete) }
      : null,
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);
  const lineasContacto = [
    { etiqueta: checkout.fullName, valor: contacto.fullName },
    { etiqueta: checkout.email, valor: contacto.email },
    { etiqueta: checkout.phone, valor: lineaDeTelefono(contacto.phone, nombrePais) },
  ].filter((linea) => linea.valor.trim() !== '');
  // Dónde lo recogen: el nombre del punto elegido, o la dirección escrita a mano.
  const lineaPunto = (traslado: DetalleTraslado | undefined) => {
    if (!traslado) return [];
    const valor = traslado.modo === 'catalogo'
      ? Object.values(puntosPorEmpresa).flat().find((p) => p.id === traslado.puntoEncuentroId)?.nombre
      : traslado.direccion;
    return valor ? [{ etiqueta: traslados.fields.puntoEncuentro, valor }] : [];
  };
  return { detalleCompra, lineasViaje, lineasContacto, lineaPunto };
}
