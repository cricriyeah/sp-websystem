'use client';

import { useSyncExternalStore } from 'react';

const CONSULTA = '(max-width: 639px)';

const suscribir = (aviso: () => void) => {
  const mq = window.matchMedia(CONSULTA);
  mq.addEventListener('change', aviso);
  return () => mq.removeEventListener('change', aviso);
};

/**
 * Menos de 640 px: el asistente de una pantalla y la barra inferior fija. En el servidor y en la
 * primera pintura vale `false` (el diseño ancho), así que nada se oculta con CSS antes de saber.
 */
export function useMovil(): boolean {
  return useSyncExternalStore(
    suscribir,
    () => window.matchMedia(CONSULTA).matches,
    () => false,
  );
}
