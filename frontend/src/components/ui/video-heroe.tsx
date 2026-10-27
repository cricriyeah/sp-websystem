'use client';

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { urlVideo } from '@/lib/media';

type Navegador = Navigator & { connection?: { saveData?: boolean } };

/**
 * Video de fondo del héroe. Va en el HTML inicial: el navegador pide el principio del archivo
 * desde que lee la página y, apenas tiene el primer cuadro, lo muestra (queda como un video
 * pausado) y arranca solo. Así no hay una foto de otra toma que se cambie por el video.
 *
 * Mientras llega el primer cuadro se ve el fondo oscuro del degradado. La foto (`respaldo`) solo
 * sale si el visitante pidió reducir el movimiento o ahorrar datos, o si el video falla: en esos
 * casos el video se desmonta y el navegador deja de descargarlo.
 *
 * `autoPlay` por sí solo no basta: React no escribe `muted` en el HTML del servidor, y un video
 * sin silencio en ese primer instante puede quedar bloqueado. Por eso, ya hidratado, se pide
 * `play()` de nuevo.
 */
export function VideoHeroe({
  src,
  className = '',
  style,
  respaldo,
}: {
  src: string;
  className?: string;
  style?: CSSProperties;
  /** La foto del héroe, ya armada por el servidor; solo se pinta cuando el video no corresponde o falla. */
  respaldo: ReactNode;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [listo, setListo] = useState(false);
  const [usarRespaldo, setUsarRespaldo] = useState(false);

  // Lee preferencias del navegador y el estado del <video>, que pudo cargar o fallar antes de
  // hidratar (esos eventos ya no se repiten). `window` no se puede leer en el render sin romper el SSR.
  useEffect(() => {
    const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ahorro = (navigator as Navegador).connection?.saveData === true;
    const el = video.current;
    if (reducir || ahorro || el?.error) {
      setUsarRespaldo(true);
      return;
    }
    if (!el) return;
    if (el.readyState >= 2) setListo(true);
    el.play().catch(() => {});
  }, []);

  if (usarRespaldo) return <>{respaldo}</>;
  return (
    <video
      ref={video}
      src={urlVideo(src, process.env.NEXT_PUBLIC_MEDIA_BASE_URL)}
      autoPlay
      muted
      loop
      playsInline
      preload="auto"
      aria-hidden="true"
      onLoadedData={() => setListo(true)}
      onError={() => setUsarRespaldo(true)}
      style={style}
      className={`transition-opacity duration-400 motion-reduce:transition-none ${listo ? 'opacity-100' : 'opacity-0'} ${className}`}
    />
  );
}
