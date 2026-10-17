'use client';

import { useEffect, useState } from 'react';

type Navegador = Navigator & { connection?: { saveData?: boolean } };

/**
 * Video de fondo que NO viaja en el HTML inicial. La imagen del héroe (LCP) ya
 * está pintada debajo; esta isla monta el `<video>` cuando la página terminó de
 * cargar y el navegador está ocioso, y lo funde sobre la imagen al disparar
 * `canplay`. No monta nada si el visitante pidió reducir el movimiento o ahorrar
 * datos: `autoPlay` anula `preload="metadata"` y el CSS no puede detenerlo.
 */
export function VideoDiferido({ src, className = '' }: { src: string; className?: string }) {
  const [montar, setMontar] = useState(false);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    const permitido = () => {
      const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const ahorro = (navigator as Navegador).connection?.saveData === true;
      return !reducir && !ahorro;
    };
    let cancelado = false;
    let idle: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const arrancar = () => {
      if (cancelado) return;
      if (typeof window.requestIdleCallback === 'function') {
        idle = window.requestIdleCallback(() => !cancelado && permitido() && setMontar(true));
      } else {
        timer = setTimeout(() => !cancelado && permitido() && setMontar(true), 200);
      }
    };
    if (document.readyState === 'complete') arrancar();
    else window.addEventListener('load', arrancar, { once: true });
    return () => {
      cancelado = true;
      window.removeEventListener('load', arrancar);
      if (idle !== undefined) window.cancelIdleCallback(idle);
      if (timer !== undefined) clearTimeout(timer);
    };
  }, []);

  if (!montar) return null;
  return (
    <video
      autoPlay
      muted
      loop
      playsInline
      aria-hidden="true"
      onCanPlay={() => setListo(true)}
      className={`transition-opacity duration-500 motion-reduce:transition-none ${listo ? 'opacity-100' : 'opacity-0'} ${className}`}
    >
      <source src={src} type="video/webm" />
    </video>
  );
}
