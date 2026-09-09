'use client';

import { useEffect, useState } from 'react';
import { getCupoRango, type DisponibilidadRango, type MotivoNoDisponible } from '@/lib/api';

/**
 * Disponibilidad de un rango de dias, para pintar en gris los que ya no admiten
 * al grupo.
 *
 * Depende de `personas` a proposito: un dia puede tener lugares libres y aun asi
 * no recibir a un grupo de 4, porque solo dos pangas de la flota pasan de 3. El
 * gris no es propiedad del dia, cambia con el tamano del grupo.
 *
 * **Falla en silencio.** Si la peticion no responde, devuelve un mapa vacio y
 * todos los dias se ven disponibles. Es ayuda adelantada: el cupo de verdad lo
 * valida el backend al cobrar, y un calendario que no carga nunca debe impedir
 * que alguien intente reservar.
 */
export function useDisponibilidad(desde: string, hasta: string, personas: number, activo = true) {
  // Se guarda junto con la consulta que lo produjo. Asi `cargando` se DERIVA de
  // comparar la clave pedida con la cargada, en vez de ponerse a mano al entrar
  // al efecto: un `setState` al inicio de un efecto provoca un render de mas y
  // React 19 lo marca como error.
  const clave = activo ? `${desde}|${hasta}|${personas}` : '';
  const [cargado, setCargado] = useState<{ clave: string; dias: DisponibilidadRango } | null>(null);

  useEffect(() => {
    if (!activo) return;
    let cancelado = false;

    getCupoRango(desde, hasta, personas)
      .then((dias) => {
        if (!cancelado) setCargado({ clave: `${desde}|${hasta}|${personas}`, dias });
      })
      .catch(() => {
        // Ver el comentario de arriba: sin respuesta no se agrisa nada. Se marca
        // como cargado igual, o el calendario se quedaria atenuado para siempre.
        if (!cancelado) setCargado({ clave: `${desde}|${hasta}|${personas}`, dias: {} });
      });

    return () => {
      cancelado = true;
    };
  }, [desde, hasta, personas, activo]);

  return {
    dias: cargado?.clave === clave ? cargado.dias : {},
    cargando: activo ? cargado?.clave !== clave : false,
  };
}

/** El motivo de ese dia, o null si cabe o si todavia no sabemos. */
export function motivoDe(
  dias: DisponibilidadRango,
  iso: string,
): MotivoNoDisponible | null {
  return dias[iso] ?? null;
}
