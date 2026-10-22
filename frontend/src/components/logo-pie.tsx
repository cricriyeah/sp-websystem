'use client';

import { useEffect, useRef } from 'react';
import Image from 'next/image';

/**
 * El logo completo del pie, en dos capas con el mismo encuadre: el isotipo da una vuelta y las letras
 * entran desde la izquierda (globals.css, `.logo-isotipo` y `.logo-letras`).
 *
 * Donde hay `animation-timeline` la animación va atada al scroll y aquí no se hace nada. Donde no la hay
 * (Safari de iPhone hasta iOS 18) se anima por tiempo al entrar el logo en pantalla: el componente marca
 * `data-anima="espera"` al montar (las capas se ocultan) y `"ya"` al verse (corren las animaciones).
 * Sin JavaScript no se marca nada y el logo queda quieto y completo.
 */
export function LogoPie() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const nodo = ref.current;
    if (!nodo || CSS.supports('animation-timeline: view()')) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    nodo.dataset.anima = 'espera';
    const observador = new IntersectionObserver(([entrada]) => {
      if (!entrada.isIntersecting) return;
      nodo.dataset.anima = 'ya';
      observador.disconnect();
    }, { threshold: 0.4 });
    observador.observe(nodo);
    return () => observador.disconnect();
  }, []);

  return (
    <div ref={ref} role="img" aria-label="Sun Baja Experience" className="relative mt-16 aspect-[286.32/91.47] w-full lg:mt-24">
      <Image src="/sunbajaexperience/logolg-isotipo.svg" alt="" fill sizes="(min-width: 1440px) 1344px, 100vw" className="logo-isotipo invert" />
      <Image src="/sunbajaexperience/logolg-letras.svg" alt="" fill sizes="(min-width: 1440px) 1344px, 100vw" className="logo-letras invert" />
    </div>
  );
}
