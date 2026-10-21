'use client';

import type { Ref } from 'react';
import { EnvelopeSimple, Phone, User } from '@phosphor-icons/react';
import { Input } from '@/components/ui/input';
import { ErrorDeCampo, propsDeError } from '@/components/ui/error-de-campo';

export type CampoContacto = 'fullName' | 'phone' | 'email';

type Props = {
  valores: Record<CampoContacto, string>;
  errores: Partial<Record<CampoContacto, string>>;
  etiquetas: Record<CampoContacto, string>;
  /** Texto gris de ejemplo (placeholder) de cada campo. */
  ejemplos?: Record<CampoContacto, string>;
  onCambio: (campo: CampoContacto, valor: string) => void;
  refs?: Partial<Record<CampoContacto, Ref<HTMLInputElement>>>;
  disabled?: boolean;
  /** Prefijo de los ids de error (`aria-describedby`), único por pantalla. */
  idPrefijo: string;
};

const CAMPOS: { campo: CampoContacto; tipo: string; icono: typeof Phone; ancho: string }[] = [
  { campo: 'fullName', tipo: 'text', icono: User, ancho: 'sm:col-span-2' },
  { campo: 'phone', tipo: 'tel', icono: Phone, ancho: 'sm:col-span-1' },
  { campo: 'email', tipo: 'email', icono: EnvelopeSimple, ancho: 'sm:col-span-1' },
];

/** Los tres datos de contacto, iguales en servicio suelto y en paquete. */
export function CamposContacto({ valores, errores, etiquetas, ejemplos, onCambio, refs, disabled, idPrefijo }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {CAMPOS.map(({ campo, tipo, icono: Icono, ancho }) => {
        const idError = `${idPrefijo}-error-${campo}`;
        const error = errores[campo];
        return (
          <label key={campo} className={`flex flex-col gap-1.5 text-base sm:text-sm ${ancho}`}>
            <span className="text-muted">{etiquetas[campo]}</span>
            <span className="relative">
              <Icono
                size={20}
                className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
              />
              <Input
                ref={refs?.[campo]}
                type={tipo}
                enterKeyHint="next"
                required
                disabled={disabled}
                value={valores[campo]}
                placeholder={ejemplos?.[campo]}
                onChange={(e) => onCambio(campo, e.target.value)}
                {...propsDeError(idError, Boolean(error))}
                className="pl-11"
              />
            </span>
            <ErrorDeCampo id={idError} mensaje={error} />
          </label>
        );
      })}
    </div>
  );
}
