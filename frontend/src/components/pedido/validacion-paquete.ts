import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { PaqueteCatalogo } from '@/lib/api';
import { fechaDeComponente } from '@/lib/calendario-paquete';
import type { EstadoPedido } from '@/lib/pedido-estado';
import { erroresPersonalizaciones } from '@/lib/personalizaciones';
import { evaluar } from '@/lib/telefono';

export type ErroresContacto = Partial<Record<'fullName' | 'phone' | 'email', string>>;

/** Errores de los tres datos de contacto del paquete (vacío = todo en orden). Función pura: no toca estado. */
export function erroresDeContacto(
  contacto: EstadoPedido['contacto'],
  checkout: Dictionary['checkout'],
): ErroresContacto {
  const errores: ErroresContacto = {};
  const nombre = contacto.fullName.trim();
  const correo = contacto.email.trim();
  if (!nombre) errores.fullName = checkout.missingFields;
  else if (/\d/.test(nombre) || !/\p{L}/u.test(nombre)) errores.fullName = checkout.invalidName;
  // `{pais}` y `{codigo}` del mensaje los llena `TelefonoCampo`, que sabe qué país está elegido.
  const telefono = evaluar(contacto.phone);
  if (telefono === 'vacio') errores.phone = checkout.missingFields;
  else if (telefono === 'codigo-desconocido') errores.phone = checkout.phoneUnknownCode;
  else if (telefono === 'incompleto') errores.phone = checkout.invalidPhone;
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
  textos: Dictionary['pedido'];
  traslados: Dictionary['traslados'];
  checkout: Dictionary['checkout'];
  /** `viaje`: fecha, extras, tipo de traslado y regreso. `datos`: dónde lo recogen. Sin `parte`, ambas. */
  parte?: 'viaje' | 'datos';
};

/** Primer error de la tarjeta de un servicio del paquete ('' = completa). Función pura: no toca estado. */
export function errorDeGrupoPaquete({
  indice, paquete, componentes, inicio, trasladoFijo, noches, textos, traslados, checkout, parte,
}: EntradaGrupo): string {
  const deViaje = parte !== 'datos';
  const deDatos = parte !== 'viaje';
  if (!inicio) return traslados.errors.seleccionaFecha;
  const item = paquete.servicios_asociados[indice];
  const actual = componentes[item.servicio.slug];
  if (deViaje) {
    const errores = erroresPersonalizaciones(item.servicio.personalizaciones, actual.extras);
    const primerError = Object.values(errores)[0];
    if (primerError) return checkout.personalizacionErrors[primerError];
  }
  const t = actual.traslado;
  if (t && trasladoFijo) {
    // Sin aeropuertos en la sede no hay qué elegir: no se exige.
    if (deViaje && (paquete.aeropuertos ?? []).length > 0 && !t.aeropuerto) return textos.airportError;
  } else if (t) {
    if (deDatos && t.modo === 'catalogo' && t.puntoEncuentroId === null) {
      return traslados.errors.seleccionaHospedaje;
    }
    if (deDatos && t.modo === 'personalizada' && !t.direccion.trim()) {
      return traslados.errors.seleccionaHospedaje;
    }
    if (deViaje && t.tipo === 'redondo_aeropuerto' && noches === null) {
      if (!t.fechaRegreso) return traslados.errors.seleccionaFechaRegreso;
      if (t.fechaRegreso <= fechaDeComponente(inicio, item.dia_estancia)) {
        return traslados.errors.seleccionaFechaRegreso;
      }
    }
  }
  return '';
}
