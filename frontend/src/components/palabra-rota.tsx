'use client';

import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { cn } from '@/components/ui/cn';

const CADA_MS = 2600;
const SALE_MS = 220;

/**
 * La palabra gigante del arranque de una sede: cambia cada 2,6 s (sale hacia arriba, entra desde
 * abajo). Es decoración: el significado lo lleva el `h1`, así que va oculta a los lectores de
 * pantalla. Con «reducir movimiento», con una sola palabra o con la pestaña oculta se queda quieta
 * en la primera, que es también lo que llega en el HTML inicial.
 */
export function PalabraRota({ palabras, className }: { palabras: string[]; className?: string }) {
  const reducido = useReducedMotion();
  const [indice, setIndice] = useState(0);
  const [fase, setFase] = useState<'quieta' | 'sale' | 'entra'>('quieta');
  const rota = !reducido && palabras.length > 1;

  useEffect(() => {
    if (!rota) return;
    let espera: ReturnType<typeof setTimeout> | undefined;
    const reloj = setInterval(() => {
      if (document.hidden) return;
      setFase('sale');
      espera = setTimeout(() => {
        setIndice((i) => (i + 1) % palabras.length);
        setFase('entra');
      }, SALE_MS);
    }, CADA_MS);
    return () => {
      clearInterval(reloj);
      clearTimeout(espera);
    };
  }, [rota, palabras.length]);

  return (
    <p aria-hidden="true" className={cn('overflow-hidden whitespace-nowrap', className)}>
      <span className={cn('inline-block', fase === 'sale' && 'palabra-sale', fase === 'entra' && 'palabra-entra')}>
        {palabras[indice % palabras.length]}
      </span>
    </p>
  );
}
