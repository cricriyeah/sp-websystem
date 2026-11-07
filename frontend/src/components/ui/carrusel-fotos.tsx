'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { useReducedMotion } from 'framer-motion';
import { cn } from '@/components/ui/cn';

const CADA_MS = 4000;

type Props = {
  fotos: { src: string; alt: string }[];
  sizes: string;
  /** La primera foto carga de inmediato; el resto, al acercarse. */
  prioridad?: boolean;
  /** Milisegundos que espera el primer cambio: que las tarjetas de una fila no cambien todas a la vez. */
  desfase?: number;
  /** Clases del zoom de la foto al pasar el mouse (cada tarjeta trae el suyo). */
  className?: string;
};

/**
 * Las fotos de un producto una sobre otra: la visible tiene opacidad 1 y las demás 0, y cada 4 s cambia
 * con un fundido (sin deslizar: la tarjeta no se mueve). Se detiene al pasar el mouse o enfocar el
 * enlace, con la pestaña oculta y con «reducir movimiento» (queda la primera). Los puntos de abajo son
 * solo un indicador: la tarjeta entera es un enlace y no puede llevar botones dentro. Sin deslizar con
 * el dedo a propósito: la fila de tarjetas ya se arrastra en horizontal y las dos cosas pelearían.
 */
export function CarruselFotos({ fotos, sizes, prioridad = false, desfase = 0, className }: Props) {
  const reducido = useReducedMotion();
  const [indice, setIndice] = useState(0);
  const [quieto, setQuieto] = useState(false);
  const rota = !reducido && fotos.length > 1;

  useEffect(() => {
    if (!rota || quieto) return;
    let reloj: ReturnType<typeof setInterval> | undefined;
    const inicio = setTimeout(() => {
      setIndice((i) => (i + 1) % fotos.length);
      reloj = setInterval(() => {
        if (!document.hidden) setIndice((i) => (i + 1) % fotos.length);
      }, CADA_MS);
    }, CADA_MS + desfase);
    return () => {
      clearTimeout(inicio);
      clearInterval(reloj);
    };
  }, [rota, quieto, desfase, fotos.length]);

  return (
    <div
      className="absolute inset-0"
      onMouseEnter={() => setQuieto(true)}
      onMouseLeave={() => setQuieto(false)}
      onFocus={() => setQuieto(true)}
      onBlur={() => setQuieto(false)}
    >
      {fotos.map((foto, i) => (
        <Image
          key={foto.src}
          src={foto.src}
          alt={i === indice ? foto.alt : ''}
          fill
          sizes={sizes}
          loading={prioridad && i === 0 ? 'eager' : 'lazy'}
          className={cn(
            'object-cover transition-[opacity,scale,transform] duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-none',
            i === indice ? 'opacity-100' : 'opacity-0',
            className,
          )}
        />
      ))}
      {fotos.length > 1 && (
        <span aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center gap-1.5">
          {fotos.map((foto, i) => (
            <span key={foto.src} className={cn('size-2 rounded-full transition-colors duration-300', i === indice ? 'bg-white' : 'bg-white/50')} />
          ))}
        </span>
      )}
    </div>
  );
}
