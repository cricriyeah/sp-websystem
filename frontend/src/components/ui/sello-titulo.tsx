import Image from 'next/image';
import { cn } from './cn';

/**
 * Cómo va el sello:
 * - `sin-aro`: el isotipo transparente, sin círculo (fondo claro).
 * - `aro-fuera`: el isotipo transparente dentro de un círculo blanco (fondo oscuro).
 * - `aro-propio`: una empresa sin isotipo transparente; su logo ya trae el círculo.
 */
export type ModoSello = 'sin-aro' | 'aro-fuera' | 'aro-propio';

type Props = { src: string; alt: string; modo: ModoSello };

/**
 * El sello de la empresa arriba a la derecha de la sección, en la misma fila que el título y alineado a su borde de
 * arriba (decisión del dueño, 2026-10-29). Mide lo suficiente para no verse perdido en la esquina, sin llegar a
 * competir con el título: 64 px en el teléfono, 80 en tableta, 96 en escritorio y 112 en pantallas anchas.
 *
 * Server Component.
 */
export function SelloTitulo({ src, alt, modo }: Props) {
  return (
    <span
      className={cn(
        'rev relative block size-16 shrink-0 sm:size-20 lg:size-24 xl:size-28',
        modo !== 'sin-aro' && 'overflow-hidden rounded-full bg-blanco',
      )}
    >
      <Image
        src={src}
        alt={alt}
        fill
        sizes="(min-width: 1280px) 112px, (min-width: 1024px) 96px, 80px"
        className={cn('object-contain', modo === 'aro-fuera' && 'p-[13.2%]', modo === 'aro-propio' && 'p-[6%]')}
      />
    </span>
  );
}
