'use client';

import type { Ref } from 'react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { CamposContacto, type CampoContacto } from '@/components/checkout/campos-contacto';

type Props = {
  /** Prefijo de los ids de los campos y sus errores (`checkout`, `traslado`). */
  idPrefijo: string;
  /** Idioma del selector de país del teléfono (nombres de países y orden). */
  lang: string;
  checkout: Dictionary['checkout'];
  valores: Record<CampoContacto, string>;
  errores: Partial<Record<CampoContacto, string>>;
  /** Para mandarle el foco al primer campo con error (lo hace `CheckoutView`); el paquete no lo usa. */
  refs?: Record<CampoContacto, Ref<HTMLInputElement>>;
  /** Con el pago en curso los datos ya no se editan; el paquete no bloquea la tarjeta de datos. */
  disabled?: boolean;
  onCambio: (campo: CampoContacto, valor: string) => void;
};

/**
 * Contenido del paso de datos (servicio suelto y traslados): nombre, teléfono
 * y correo. Sin estado propio: `contact` y los errores viven en la vista (el
 * código promocional, la reserva y la recuperación los leen), así que plegar
 * la tarjeta no pierde lo escrito.
 */
export function BloqueContacto({ idPrefijo, lang, checkout, valores, errores, refs, disabled, onCambio }: Props) {
  return (
    <CamposContacto
      idPrefijo={idPrefijo}
      valores={valores}
      errores={errores}
      etiquetas={{ phone: checkout.phone, fullName: checkout.fullName, email: checkout.email }}
      ejemplos={checkout.contactExamples}
      telefono={{
        lang,
        textos: {
          phoneCountry: checkout.phoneCountry,
          phoneCountrySearch: checkout.phoneCountrySearch,
          phoneCountryNone: checkout.phoneCountryNone,
          phoneCountryNoneHint: checkout.phoneCountryNoneHint,
          phoneCountryFrequent: checkout.phoneCountryFrequent,
          phoneCountryAll: checkout.phoneCountryAll,
          phoneCountryCount: checkout.phoneCountryCount,
          phoneCountryCountOne: checkout.phoneCountryCountOne,
          phoneCountryChanged: checkout.phoneCountryChanged,
          phonePlaceholderOther: checkout.phonePlaceholderOther,
          cerrar: checkout.barra.cerrar,
        },
      }}
      refs={refs}
      disabled={disabled}
      onCambio={onCambio}
    />
  );
}
