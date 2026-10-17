import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { PaqueteCatalogo } from '@/lib/api';
import { fechaDeComponente } from '@/lib/calendario-paquete';
import type { EstadoPedido } from '@/lib/pedido-estado';
import { zonaEfectivaDeTraslado } from '@/lib/pedido-payload';
import { erroresPersonalizaciones } from '@/lib/personalizaciones';

export type ErroresContacto = Partial<Record<'fullName' | 'phone' | 'email', string>>;

/** Errores de los tres datos de contacto del paquete (vacío = todo en orden). Función pura: no toca estado. */
export function erroresDeContacto(
  contacto: EstadoPedido['contacto'],
  checkout: Dictionary['checkout'],
): ErroresContacto {
  const errores: ErroresContacto = {};
  const nombre = contacto.fullName.trim();
  const telefono = contacto.phone.trim();
  const correo = contacto.email.trim();
  if (!nombre) errores.fullName = checkout.missingFields;
  else if (/\d/.test(nombre) || !/\p{L}/u.test(nombre)) errores.fullName = checkout.invalidName;
  if (!telefono) errores.phone = checkout.missingFields;
  else if (!/^[\d\s+()\-.]+$/.test(telefono) || !/^\d{10,15}$/.test(telefono.replace(/\D/g, ''))) {
    errores.phone = checkout.invalidPhone;
  }
  if (!correo) errores.email = checkout.missingFields;
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo)) errores.email = checkout.invalidEmail;
  return errores;
}

type EntradaGrupo = {
  indice: number;
  paquete: PaqueteCatalogo;
  componentes: EstadoPedido['componentes'];
  inicio: string | null;
  trasladoFijo: boolean;
  noches: number | null;
  zonaDePunto: Parameters<typeof zonaEfectivaDeTraslado>[1];
  textos: Dictionary['pedido'];
  traslados: Dictionary['traslados'];
  checkout: Dictionary['checkout'];
};

/** Primer error de la tarjeta de un servicio del paquete ('' = completa). Función pura: no toca estado. */
export function errorDeGrupoPaquete({
  indice, paquete, componentes, inicio, trasladoFijo, noches, zonaDePunto, textos, traslados, checkout,
}: EntradaGrupo): string {
  if (!inicio) return traslados.errors.seleccionaFecha;
  const item = paquete.servicios_asociados[indice];
  const actual = componentes[item.servicio.slug];
  const errores = erroresPersonalizaciones(item.servicio.personalizaciones, actual.extras);
  const primerError = Object.values(errores)[0];
  if (primerError) return checkout.personalizacionErrors[primerError];
  const t = actual.traslado;
  if (t && trasladoFijo) {
    if (!t.aeropuerto) return textos.airportError;
  } else if (t) {
    if (t.modo === 'catalogo' && t.puntoEncuentroId === null) {
      return traslados.errors.seleccionaHospedaje;
    }
    if (t.modo === 'personalizada' && !t.direccion.trim()) {
      return traslados.errors.seleccionaHospedaje;
    }
    if (t.tipo === 'redondo_actividad' && !zonaEfectivaDeTraslado(t, zonaDePunto)) {
      return traslados.errors.seleccionaZona;
    }
    if (t.tipo === 'redondo_aeropuerto' && noches === null) {
      if (!t.fechaRegreso) return traslados.errors.seleccionaFechaRegreso;
      if (t.fechaRegreso <= fechaDeComponente(inicio, item.dia_estancia)) {
        return traslados.errors.seleccionaFechaRegreso;
      }
    }
  }
  return '';
}
