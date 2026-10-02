export type CampoValidacion = 'personas' | 'hora' | 'fecha' | 'traslado' | 'contacto';

/** El backend devuelve errores de formulario por campo; nunca mostramos detalles técnicos. */
export function campoDeValidacion(detalle: unknown): CampoValidacion | null {
  if (!detalle || typeof detalle !== 'object' || Array.isArray(detalle)) return null;
  if ('numero_personas' in detalle) return 'personas';
  if ('hora' in detalle) return 'hora';
  if ('fecha' in detalle || 'fecha_salida' in detalle || 'fecha_regreso' in detalle) return 'fecha';
  if ('punto_encuentro' in detalle || 'zona' in detalle || 'tipo_traslado' in detalle || 'direccion_personalizada' in detalle) {
    return 'traslado';
  }
  if ('nombre_cliente' in detalle || 'telefono_cliente' in detalle || 'correo_cliente' in detalle) return 'contacto';
  return null;
}
