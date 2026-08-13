import { Camera, VideoCamera } from '@phosphor-icons/react/ssr';

type MediaPlaceholderProps = {
  /** Que foto/video va aqui. Se muestra: sirve de lista de tomas para el cliente. */
  hint: string;
  aspect?: 'video' | 'square' | 'portrait' | 'wide';
  kind?: 'photo' | 'video';
};

const PROPORCIONES = {
  video: 'aspect-video',
  square: 'aspect-square',
  portrait: 'aspect-[3/4]',
  wide: 'aspect-[21/9]',
};

/**
 * Hueco para material que todavia no existe.
 *
 * Muestra a proposito la descripcion de la toma: mientras no haya fotos sirve de
 * lista de pendientes para quien las va a tomar, y deja claro en la pagina que
 * es un espacio reservado y no una imagen rota. Al llegar el material, se
 * reemplaza este componente por un <Image> con el mismo encuadre.
 */
export function MediaPlaceholder({ hint, aspect = 'video', kind = 'photo' }: MediaPlaceholderProps) {
  const Icono = kind === 'video' ? VideoCamera : Camera;

  return (
    <div
      className={`flex ${PROPORCIONES[aspect]} w-full flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border bg-surface/60 p-6 text-center`}
    >
      <Icono size={22} className="text-muted/70" />
      <p className="max-w-[28ch] text-xs leading-relaxed text-muted">{hint}</p>
    </div>
  );
}
