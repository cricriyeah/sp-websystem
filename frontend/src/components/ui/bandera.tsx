'use client';

import { useState } from 'react';
import Image from 'next/image';
import { Globe } from '@phosphor-icons/react';
import { cn } from './cn';

/**
 * Bandera de un país, decorativa (`alt=""`): el nombre y el código siempre van en texto al lado.
 * Los SVG viven en `public/flags/<ISO>.svg` (los copia `npm run banderas`) y se piden sin
 * optimizar: ya son vectores de 0,6 a 3,4 KB. La caja 3:2 mide lo mismo antes y después de que
 * llegue el archivo, así que nada se mueve; hasta entonces se ve el fondo arena.
 *
 * Sin archivo (sigla inválida o un 404) se pinta un icono `Globe` en la misma caja. El borde es
 * un contorno hacia dentro para que la bandera blanca (Japón, Finlandia) no se pierda en un
 * campo blanco sin achicar la imagen. Esquinas rectas, como el resto del campo.
 */
type Tam = 'm' | 's';

const CAJA: Record<Tam, { clase: string; ancho: number; alto: number; icono: number }> = {
  m: { clase: 'h-4 w-6', ancho: 24, alto: 16, icono: 14 },
  s: { clase: 'h-3.5 w-5', ancho: 20, alto: 14, icono: 12 },
};

type BanderaProps = {
  /** Sigla ISO 3166-1 alfa-2 en mayúsculas, p. ej. `MX`. */
  iso: string;
  tam?: Tam;
  /** La del disparador carga con la página; las de la lista, de forma diferida. */
  prioritaria?: boolean;
  className?: string;
};

export function Bandera({ iso, tam = 'm', prioritaria = false, className }: BanderaProps) {
  const [fallo, setFallo] = useState(false);
  const caja = CAJA[tam];
  // La sigla forma parte de una ruta: solo dos letras, nunca texto libre.
  const hayArchivo = /^[A-Z]{2}$/.test(iso) && !fallo;

  return (
    <span
      aria-hidden="true"
      className={cn(
        'relative inline-flex shrink-0 items-center justify-center overflow-hidden bg-cafe-bruma outline outline-1 -outline-offset-1 outline-borde',
        caja.clase,
        className,
      )}
    >
      {hayArchivo ? (
        <Image
          src={`/flags/${iso}.svg`}
          alt=""
          width={caja.ancho}
          height={caja.alto}
          unoptimized
          loading={prioritaria ? 'eager' : 'lazy'}
          onError={() => setFallo(true)}
          className="size-full object-cover"
        />
      ) : (
        <Globe size={caja.icono} aria-hidden="true" className="text-muted" />
      )}
    </span>
  );
}
