'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';

type Props = { fotos: readonly string[]; sizes: string; className?: string };

/**
 * Una foto distinta en cada visita. El servidor pinta la primera (la página es estática y el azar en el
 * servidor rompería la hidratación); al montar se elige una al azar y entra con un fundido.
 * Decorativa: `alt` vacío.
 */
export function FotoAleatoria({ fotos, sizes, className }: Props) {
  const [indice, setIndice] = useState<number | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- el azar solo puede elegirse en el navegador
    setIndice(Math.floor(Math.random() * fotos.length));
  }, [fotos.length]);

  return (
    <Image
      key={indice ?? -1}
      src={fotos[indice ?? 0]}
      alt=""
      fill
      sizes={sizes}
      loading="lazy"
      className={`object-cover motion-safe:animate-[aparecer_600ms_ease-out] ${className ?? ''}`}
    />
  );
}
