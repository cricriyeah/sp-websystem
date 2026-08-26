'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { useReducedMotion } from 'motion/react';

type HeroCarouselProps = {
  fotos: string[];
};

/** Cuanto dura cada foto en pantalla antes de pasar a la siguiente. */
const INTERVALO_MS = 6000;
/** Duracion del cruce entre una foto y la siguiente. */
const DURACION_TRANSICION_MS = 1200;

/**
 * Fondo de la portada: las fotos rotan solas, sin flechas ni puntos — es
 * ambiente detras del titular, no una pieza que el cliente tenga que operar.
 *
 * Todas las fotos se montan de una vez, apiladas con `opacity`, y solo la
 * activa llega a 1. Cambiar de foto es entonces un cruce de opacidad en vez de
 * desmontar/montar `<Image>`, que evita el parpadeo de un pintado en blanco
 * entre una y otra.
 *
 * Con `prefers-reduced-motion` no rota: se queda quieta en la primera. Mover
 * contenido solo y en paralelo a un texto que se esta leyendo es justo lo que
 * esa preferencia pide evitar (WCAG 2.2.2, "Pause, Stop, Hide").
 */
export function HeroCarousel({ fotos }: HeroCarouselProps) {
  const [activa, setActiva] = useState(0);
  const sinMovimiento = useReducedMotion();

  useEffect(() => {
    if (sinMovimiento || fotos.length < 2) return;
    const id = setInterval(() => {
      setActiva((i) => (i + 1) % fotos.length);
    }, INTERVALO_MS);
    return () => clearInterval(id);
  }, [fotos.length, sinMovimiento]);

  return (
    <>
      {fotos.map((foto, i) => (
        <Image
          key={foto}
          src={foto}
          // Decorativa: es el fondo detras del titular, que ya dice de que va
          // el sitio. Describirla aqui seria repetir en voz alta lo que la foto
          // ilustra sin agregar informacion nueva.
          alt=""
          fill
          priority={i === 0}
          sizes="100vw"
          className="object-cover transition-opacity ease-in-out"
          style={{
            opacity: i === activa ? 1 : 0,
            transitionDuration: `${DURACION_TRANSICION_MS}ms`,
          }}
        />
      ))}
    </>
  );
}
