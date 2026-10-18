'use client';

import { useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { conPaso, decidirPaso, pasoDeQuery } from '@/lib/paso-url';
import type { PasoId } from '@/lib/pasos-checkout';

type Opciones = {
  /** Paso más avanzado alcanzado. */
  actual: PasoId;
  /** Paso anterior que el cliente reabrió (con «Modificar» o con Atrás). */
  editando: PasoId | null;
  setEditando: (paso: PasoId | null) => void;
  /** Hay un pago en curso: lo anterior no se puede cambiar, Atrás vuelve a Pago. */
  bloqueado: boolean;
  /** Hasta que el borrador y la reserva recuperada se hayan repuesto, la URL no manda. */
  habilitado: boolean;
};

const leerPasoDeLaUrl = (): PasoId | null =>
  pasoDeQuery(new URLSearchParams(window.location.search).get('paso'));

/**
 * El paso vive en `?paso=` y cada paso es una entrada de historial (`pushState`; el router de
 * Next lo integra con `useSearchParams` sin repedir la página al servidor). Atrás reabre el
 * paso anterior, Adelante lo cierra, y un paso al que no se ha llegado se reescribe al último
 * válido. `router.push` queda para cambiar de ruta o de idioma.
 */
export function usePasoUrl({ actual, editando, setEditando, bloqueado, habilitado }: Opciones): void {
  const urlPaso = pasoDeQuery(useSearchParams().get('paso'));
  const objetivo = editando ?? actual;
  // Lo último que este hook vio o escribió en la URL: distingue «la URL cambió» (Atrás) de
  // «el estado cambió» (el cliente confirmó un paso) sin leer el historial.
  const ultimo = useRef<PasoId | null | undefined>(undefined);

  // URL → estado.
  useEffect(() => {
    if (!habilitado) return;
    const primera = ultimo.current === undefined;
    if (!primera && ultimo.current === urlPaso) return;
    ultimo.current = urlPaso;
    // Entrada sin `?paso=` (enlace del sitio): manda el estado; el otro efecto escribe la URL.
    if (primera && urlPaso === null) return;
    const decision = decidirPaso(urlPaso, actual, bloqueado);
    if (decision.tipo === 'redirigir') {
      ultimo.current = decision.a;
      window.history.replaceState(null, '', conPaso(window.location.search, decision.a));
    } else if (decision.tipo === 'editar') {
      setEditando(decision.paso);
    } else if (decision.tipo === 'cerrarEdicion') {
      setEditando(null);
    }
  }, [habilitado, urlPaso, actual, bloqueado, setEditando]);

  // Estado → URL: confirmar un paso o reabrir uno escribe una entrada de historial.
  const sincronizada = useRef(false);
  useEffect(() => {
    if (!habilitado) return;
    // La primera vez solo se alinea la URL con el estado repuesto (borrador, reserva recuperada)
    // sin sumar una entrada: de otro modo Atrás saldría de la compra.
    const primera = !sincronizada.current;
    sincronizada.current = true;
    const enUrl = leerPasoDeLaUrl();
    if (enUrl === objetivo || (enUrl === null && objetivo === 'viaje')) return;
    ultimo.current = objetivo;
    const nueva = conPaso(window.location.search, objetivo);
    if (primera) window.history.replaceState(null, '', nueva);
    else window.history.pushState(null, '', nueva);
  }, [habilitado, objetivo]);
}
