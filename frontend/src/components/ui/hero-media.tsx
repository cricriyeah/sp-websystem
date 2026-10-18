import Image from 'next/image';
import type { ReactNode } from 'react';
import { VideoDiferido } from '@/components/ui/video-diferido';

type HeroMediaProps = {
  /** Foto del héroe: es el LCP, va en el HTML inicial. `null` si la sede aún no tiene. */
  imagen: string | null;
  /** Video de fondo: se monta después de `load`, encima de la imagen. `null` = solo imagen. */
  video: string | null;
  /** Descripción de la imagen; vacío (`''`) si es decorativa. */
  alt: string;
  /** `preload` de `next/image`: verdadero en el héroe de la página, que es el LCP. */
  preload?: boolean;
  /** `object-position` de la imagen y del video, para encuadrar distinto por sede. */
  objectPosition?: string;
  /** Contenido del héroe (título, subtítulo, selector…), apilado sobre el degradado. */
  children: ReactNode;
};

/**
 * Fondo de un héroe: imagen inmediata (`<Image preload>`), video diferido encima,
 * degradado `--scrim-hero` para que el texto nunca vaya directo sobre la foto, y
 * el alto mínimo con el que se pinta el contenido. La isla cliente
 * `VideoDiferido` no monta nada con «reducir movimiento» ni con ahorro de datos,
 * así que en esos casos queda solo la imagen.
 *
 * Server Component: no necesita JavaScript propio.
 */
export function HeroMedia({ imagen, video, alt, preload = false, objectPosition, children }: HeroMediaProps) {
  const posicion = objectPosition ? { objectPosition } : undefined;
  return (
    <div className="relative w-full overflow-hidden">
      {imagen ? (
        <Image
          src={imagen}
          alt={alt}
          fill
          sizes="100vw"
          preload={preload}
          className="object-cover"
          style={posicion}
        />
      ) : null}
      {video ? (
        <VideoDiferido src={video} className="absolute inset-0 h-full w-full object-cover" style={posicion} />
      ) : null}
      <div className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />

      <div className="relative flex min-h-[70dvh] flex-col justify-end lg:min-h-[80dvh]">
        {children}
      </div>
    </div>
  );
}
