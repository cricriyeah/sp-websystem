import type { Moneda, PaqueteCatalogo } from './api';
import type { ComponentePedido, DatosContacto, DetalleTraslado } from './pedido-payload';
import { seleccionInicial, type SeleccionPersonalizacion } from './personalizaciones';

export type EstadoPedido = {
  contacto: DatosContacto;
  inicio: string | null;
  hora: string;
  moneda: Moneda;
  formaPago: 'completo' | 'anticipo';
  componentes: Record<string, ComponentePedido>;
};

export type AccionPedido =
  | { tipo: 'contacto'; cambios: Partial<DatosContacto> }
  | { tipo: 'inicio'; valor: string }
  | { tipo: 'hora'; valor: string }
  | { tipo: 'moneda'; valor: Moneda }
  | { tipo: 'formaPago'; valor: 'completo' | 'anticipo' }
  | { tipo: 'personas'; slug: string; valor: number }
  | { tipo: 'extras'; slug: string; valor: SeleccionPersonalizacion[] }
  | { tipo: 'traslado'; slug: string; cambios: Partial<DetalleTraslado> };

export type OpcionesEstadoInicial = {
  moneda: Moneda;
  puntoInicial: (empresaSlug: string) => number | null;
};

export function estadoInicial(paquete: PaqueteCatalogo, opciones: OpcionesEstadoInicial): EstadoPedido {
  const componentes: Record<string, ComponentePedido> = {};
  for (const c of paquete.servicios_asociados) {
    componentes[c.servicio.slug] = {
      personas: c.personas_incluidas,
      extras: seleccionInicial(c.servicio.personalizaciones),
      ...(c.servicio.tipo_servicio === 'transporte'
        ? {
            traslado: {
              tipo: 'redondo_actividad' as const,
              modo: 'catalogo' as const,
              puntoEncuentroId: opciones.puntoInicial(c.servicio.empresa_slug),
              direccion: '',
              zonaLibre: '' as const,
              fechaRegreso: null,
            },
          }
        : {}),
    };
  }
  return {
    contacto: { fullName: '', phone: '', email: '' },
    inicio: null,
    hora: '07:00',
    moneda: opciones.moneda,
    formaPago: 'completo',
    componentes,
  };
}

function conComponente(
  estado: EstadoPedido,
  slug: string,
  cambiar: (c: ComponentePedido) => ComponentePedido,
): EstadoPedido {
  return { ...estado, componentes: { ...estado.componentes, [slug]: cambiar(estado.componentes[slug]) } };
}

export function reducirPedido(estado: EstadoPedido, accion: AccionPedido): EstadoPedido {
  switch (accion.tipo) {
    case 'contacto':
      return { ...estado, contacto: { ...estado.contacto, ...accion.cambios } };
    case 'inicio':
      return { ...estado, inicio: accion.valor };
    case 'hora':
      return { ...estado, hora: accion.valor };
    case 'moneda':
      return { ...estado, moneda: accion.valor };
    case 'formaPago':
      return { ...estado, formaPago: accion.valor };
    case 'personas':
      return conComponente(estado, accion.slug, (c) => ({ ...c, personas: accion.valor }));
    case 'extras':
      return conComponente(estado, accion.slug, (c) => ({ ...c, extras: accion.valor }));
    case 'traslado':
      return conComponente(estado, accion.slug, (c) =>
        c.traslado ? { ...c, traslado: { ...c.traslado, ...accion.cambios } } : c,
      );
  }
}
