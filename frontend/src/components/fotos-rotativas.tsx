'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { cn } from '@/components/ui/cn';

type Props = {
  fotos: { src: string; alt: string }[];
  sizes: string;
  /** Milisegundos que se queda cada foto. */
  intervalo?: number;
  className?: string;
};

/**
 * Fotos apiladas que cambian solas con un fundido; no se arrastran ni tienen controles. Con «reducir
 * movimiento», con la pestaña oculta o con una sola foto se queda quieta en la primera.
 */
export function FotosRotativas({ fotos, sizes, intervalo = 5000, className }: Props) {
  const [actual, setActual] = useState(0);

  useEffect(() => {
    if (fotos.length < 2 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const id = window.setInterval(() => {
      if (!document.hidden) setActual((i) => (i + 1) % fotos.length);
    }, intervalo);
    return () => window.clearInterval(id);
  }, [fotos.length, intervalo]);

  return fotos.map((foto, i) => (
    <Image
      key={foto.src}
      src={foto.src}
      alt={i === actual ? foto.alt : ''}
      aria-hidden={i === actual ? undefined : true}
      fill
      sizes={sizes}
      loading="lazy"
      className={cn(
        'object-cover transition-opacity duration-[1200ms] ease-[var(--curva-estandar)] motion-reduce:transition-none',
        i === actual ? 'opacity-100' : 'opacity-0',
        className,
      )}
    />
  ));
}
