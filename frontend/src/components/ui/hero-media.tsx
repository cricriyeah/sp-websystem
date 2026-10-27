import Image from 'next/image';
import type { CSSProperties, ReactNode } from 'react';
import { VideoHeroe } from '@/components/ui/video-heroe';

type HeroMediaProps = {
  /** Foto del héroe. Sin video es el LCP y va en el HTML inicial; con video es solo el respaldo. `null` si la sede aún no tiene. */
  imagen: string | null;
  /** Video de fondo: va en el HTML inicial y es lo primero que se pinta. `null` = solo imagen. */
  video: string | null;
  /** Descripción de la imagen; vacío (`''`) si es decorativa. */
  alt: string;
  /** `preload` de `next/image`: verdadero en el héroe de la página, que es el LCP. */
  preload?: boolean;
  /** `object-position` de la imagen y del video, para encuadrar distinto por sede. */
  objectPosition?: string;
  /** `object-position` solo bajo 640 px; sin él, el de `objectPosition`. */
  objectPositionMovil?: string;
  /** `object-position` del video solo bajo 640 px; sin él, el mismo encuadre de la imagen. */
  objectPositionVideoMovil?: string;
  /**
   * `pantalla` (por defecto): alto mínimo de 70-80 % de la pantalla. `contenido`: el alto lo da el
   * contenido, con tope para que lo de abajo asome al menos 120 px. `completo` (campaña, F10): toda la pantalla, desde el borde de arriba: la barra flota encima, así que el contenido se aparta con `--nav-alto`. `media` (detalles de servicio y paquete): 70 % de la pantalla.
   */
  alto?: 'pantalla' | 'contenido' | 'completo' | 'media';
  /** Contenido del héroe (título, subtítulo, selector…), apilado sobre el degradado. */
  children: ReactNode;
};

/**
 * Fondo de un héroe: con video, el video desde el primer instante (su primer cuadro se ve como
 * un video pausado y arranca solo) y la foto solo de respaldo; sin video, la foto inmediata
 * (`<Image preload>`). Encima, el degradado `--scrim-hero` para que el texto nunca vaya directo
 * sobre el fondo, y el alto mínimo con el que se pinta el contenido. La isla cliente `VideoHeroe`
 * cambia el video por la foto con «reducir movimiento», con ahorro de datos o si el video falla.
 *
 * Server Component: no necesita JavaScript propio.
 */
export function HeroMedia({ imagen, video, alt, preload = false, objectPosition, objectPositionMovil, objectPositionVideoMovil, alto = 'pantalla', children }: HeroMediaProps) {
  const posicion = objectPosition || objectPositionMovil
    ? ({ '--pos': objectPosition ?? '50% 50%', '--pos-m': objectPositionMovil ?? objectPosition ?? '50% 50%' } as CSSProperties)
    : undefined;
  const ENCUADRE = '[object-position:var(--pos)] max-sm:[object-position:var(--pos-m)]';
  const claseEncuadre = posicion ? ENCUADRE : '';
  // El video puede necesitar su propio encuadre móvil: lo que sigue la cámara no está donde está lo bonito de la foto.
  const posicionVideo = objectPositionVideoMovil
    ? ({ '--pos': objectPosition ?? '50% 50%', '--pos-m': objectPositionVideoMovil } as CSSProperties)
    : posicion;
  // Con video, la foto es solo el respaldo (no se precarga): lo primero que se pinta es el video.
  const foto = imagen ? (
    <Image
      src={imagen}
      alt={alt}
      fill
      sizes="100vw"
      preload={preload && !video}
      className={`object-cover ${claseEncuadre}`}
      style={posicion}
    />
  ) : null;
  return (
    // `bg-tinta` solo con video: es el fondo que se ve hasta que llega su primer cuadro.
    <div className={`relative w-full overflow-hidden ${video ? 'bg-tinta' : ''}`}>
      {video ? (
        <VideoHeroe src={video} className={`absolute inset-0 h-full w-full object-cover ${posicionVideo ? ENCUADRE : ''}`} style={posicionVideo} respaldo={foto} />
      ) : foto}
      <div className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />

      <div
        className={
          alto === 'pantalla'
            ? 'relative flex min-h-[70dvh] flex-col justify-end lg:min-h-[80dvh]'
            : alto === 'completo'
              ? 'relative flex min-h-[max(34rem,100svh)] max-h-[62.5rem] flex-col justify-end'
              : alto === 'media'
                ? 'relative flex min-h-[max(28.75rem,min(70svh,45rem))] flex-col justify-end'
                : 'relative flex max-h-[calc(100svh-120px)] flex-col justify-end'
        }
      >
        {children}
      </div>
    </div>
  );
}
