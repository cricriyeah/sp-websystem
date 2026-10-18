'use client';

import { useEffect, useRef, useState } from 'react';
import { borrarBorrador, guardarBorrador, leerBorrador } from '@/lib/borrador-reserva';

type Opciones<T> = {
  clave: string;
  /** Falso mientras otra cosa decide el estado inicial (p. ej. recuperar la reserva del servidor). */
  habilitado: boolean;
  /** Lo que se guarda; se vuelve a guardar cada vez que cambia su contenido. */
  estado: T;
  /** Repone el estado desde lo guardado. */
  restaurar: (guardado: T) => void;
  /** Solo se repone el borrador si la URL lleva `?paso=` (recarga, cambio de idioma, Atrás). */
  reponer: boolean;
  /** Pago confirmado: ya no hay nada que conservar. */
  terminado: boolean;
};

/**
 * Borrador de la pestaña (ver `lib/borrador-reserva.ts`). Devuelve `listo`: cierto cuando ya se
 * intentó reponer, para que lo que depende del estado (el paso en la URL) espere a eso.
 */
export function useBorrador<T>({ clave, habilitado, estado, restaurar, reponer, terminado }: Opciones<T>): boolean {
  const [listo, setListo] = useState(false);
  const restaurarRef = useRef(restaurar);
  useEffect(() => { restaurarRef.current = restaurar; });

  useEffect(() => {
    if (!habilitado || listo) return;
    if (reponer) {
      const guardado = leerBorrador<T>(clave);
      if (guardado) restaurarRef.current(guardado);
    } else {
      // Entrada nueva desde el sitio: lo que vino en el enlace manda sobre un borrador viejo.
      borrarBorrador(clave);
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- una sola vez, tras reponer el borrador
    setListo(true);
  }, [habilitado, listo, clave, reponer]);

  const serial = JSON.stringify(estado);
  useEffect(() => {
    if (!listo) return;
    if (terminado) borrarBorrador(clave);
    else guardarBorrador(clave, JSON.parse(serial));
  }, [listo, terminado, clave, serial]);

  return listo;
}
