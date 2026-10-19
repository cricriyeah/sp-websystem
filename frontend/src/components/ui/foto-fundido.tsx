'use client';

import { useEffect, useRef, useState, type ComponentProps } from 'react';
import Image from 'next/image';
import { cn } from './cn';

/**
 * `next/image` que entra con un fundido de opacidad de 250 ms al cargar (sin movimiento con
 * «reducir movimiento»). Si la foto ya venía en caché y cargó antes de hidratar, se muestra
 * de inmediato.
 */
export function FotoFundido({ alt, className, onLoad, ...props }: ComponentProps<typeof Image>) {
  const ref = useRef<HTMLImageElement>(null);
  const [cargada, setCargada] = useState(false);

  useEffect(() => {
    if (ref.current?.complete) setCargada(true);
  }, []);

  return (
    <Image
      {...props}
      alt={alt}
      ref={ref}
      onLoad={(evento) => {
        setCargada(true);
        onLoad?.(evento);
      }}
      className={cn('transition-opacity duration-[250ms] motion-reduce:transition-none', cargada ? 'opacity-100' : 'opacity-0', className)}
    />
  );
}
