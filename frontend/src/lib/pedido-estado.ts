import type { Moneda, PaqueteCatalogo } from './api';
import type { ComponentePedido, DatosContacto, DetalleTraslado } from './pedido-payload';
import { seleccionInicial, type SeleccionPersonalizacion } from './personalizaciones';
import { maxPersonasPaquete } from './pedido-paquete';

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
  | { tipo: 'personasPaquete'; slugPrincipal: string; valor: number }
  | { tipo: 'personasLogistica'; slug: string; slugPrincipal: string; valor: number }
  | { tipo: 'extras'; slug: string; valor: SeleccionPersonalizacion[] }
  | { tipo: 'traslado'; slug: string; cambios: Partial<DetalleTraslado> };

export type OpcionesEstadoInicial = {
  moneda: Moneda;
  puntoInicial: (empresaSlug: string) => number | null;
};

export function estadoInicial(paquete: PaqueteCatalogo, opciones: OpcionesEstadoInicial): EstadoPedido {
  const componentes: Record<string, ComponentePedido> = {};
  const personasPaquete = paquete.precio_por_persona ? maxPersonasPaquete(paquete) : null;
  for (const c of paquete.servicios_asociados) {
    componentes[c.servicio.slug] = {
      personas: personasPaquete ?? c.personas_incluidas,
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
    case 'personasPaquete':
      return { ...estado, componentes: Object.fromEntries(
        Object.entries(estado.componentes).map(([slug, c]) => [slug, {
          ...c, personas: slug === accion.slugPrincipal ? accion.valor : Math.min(c.personas, accion.valor),
        }]),
      ) };
    case 'personasLogistica':
      if (accion.slug === accion.slugPrincipal || !estado.componentes[accion.slugPrincipal]) return estado;
      return conComponente(estado, accion.slug,
        (c) => ({ ...c, personas: Math.max(1, Math.min(accion.valor, estado.componentes[accion.slugPrincipal].personas)) }));
    case 'extras':
      return conComponente(estado, accion.slug, (c) => ({ ...c, extras: accion.valor }));
    case 'traslado':
      return conComponente(estado, accion.slug, (c) =>
        c.traslado ? { ...c, traslado: { ...c.traslado, ...accion.cambios } } : c,
      );
  }
}
