'use client';

import type { Ref } from 'react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { CamposContacto, type CampoContacto } from '@/components/checkout/campos-contacto';

type Props = {
  checkout: Dictionary['checkout'];
  valores: Record<CampoContacto, string>;
  errores: Partial<Record<CampoContacto, string>>;
  /** Para mandarle el foco al primer campo con error (lo hace `CheckoutView`). */
  refs: Record<CampoContacto, Ref<HTMLInputElement>>;
  /** Con el pago en curso los datos ya no se editan. */
  disabled: boolean;
  onCambio: (campo: CampoContacto, valor: string) => void;
};

/**
 * Contenido del paso de datos del servicio suelto: nombre, teléfono y correo.
 * Sin estado propio: `contact` y `erroresCampo` viven en `CheckoutView` (el
 * código promocional, la reserva y la recuperación los leen), así que plegar
 * la tarjeta no pierde lo escrito.
 */
export function BloqueContacto({ checkout, valores, errores, refs, disabled, onCambio }: Props) {
  return (
    <CamposContacto
      idPrefijo="checkout"
      valores={valores}
      errores={errores}
      etiquetas={{ phone: checkout.phone, fullName: checkout.fullName, email: checkout.email }}
      ejemplos={checkout.contactExamples}
      refs={refs}
      disabled={disabled}
      onCambio={onCambio}
    />
  );
}
