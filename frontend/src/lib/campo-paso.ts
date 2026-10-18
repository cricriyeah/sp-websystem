// A qué paso del checkout pertenece cada campo que el servidor puede rechazar (400 con errores
// por campo) y a qué control del formulario hay que llevar al cliente. Puro: sin React.
import type { PasoId } from './pasos-checkout';

const VIAJE = new Set([
  'personas', 'numero_personas', 'hora', 'fecha', 'fecha_salida', 'fecha_regreso', 'tipo_traslado',
  'personalizaciones', 'servicio',
]);
const DATOS = new Set([
  'contacto', 'nombre_cliente', 'telefono_cliente', 'correo_cliente',
  'traslado', 'punto_encuentro', 'direccion_personalizada', 'zona',
]);

/** El paso al que pertenece `campo`; lo que no se reconoce (deslinde, tarjeta, código) es de Pago. */
export function pasoDeCampo(campo: string): PasoId {
  if (VIAJE.has(campo)) return 'viaje';
  if (DATOS.has(campo)) return 'datos';
  return 'pago';
}

/** Los tres datos de contacto: el control se encuentra por el id de su error (`<prefijo>-error-<campo>`). */
const CONTACTO: Record<string, string> = {
  nombre_cliente: 'fullName',
  telefono_cliente: 'phone',
  correo_cliente: 'email',
};

export type DestinoError = { paso: PasoId; campo: string };

/**
 * A dónde llevar al cliente cuando el servidor rechaza un campo. `idPrefijo` es el de
 * `CamposContacto` de la ruta (`checkout`, `traslado`, `pedido`). `campo` es el id de un
 * elemento o de su error (el control lo referencia con `aria-describedby`); vacío si el
 * campo no es un control enfocable (una fecha): basta abrir su paso.
 */
export function destinoDeError(detalle: unknown, idPrefijo: string): DestinoError | null {
  if (!detalle || typeof detalle !== 'object' || Array.isArray(detalle)) return null;
  const claves = Object.keys(detalle).filter((clave) => pasoDeCampo(clave) !== 'pago');
  if (claves.length === 0) return null;
  // El primer paso del flujo manda: se corrige de arriba abajo.
  const ordenadas = [...claves].sort((a, b) => (pasoDeCampo(a) === 'viaje' ? 0 : 1) - (pasoDeCampo(b) === 'viaje' ? 0 : 1));
  const clave = ordenadas[0];
  const contacto = CONTACTO[clave];
  return { paso: pasoDeCampo(clave), campo: contacto ? `${idPrefijo}-error-${contacto}` : '' };
}
