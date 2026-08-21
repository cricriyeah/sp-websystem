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
export function useDisponibilidad(desde: string, hasta: string, personas: number) {
  const [dias, setDias] = useState<DisponibilidadRango>({});

  useEffect(() => {
    let cancelado = false;

    getCupoRango(desde, hasta, personas)
      .then((mapa) => {
        if (!cancelado) setDias(mapa);
      })
      .catch(() => {
        // Ver el comentario de arriba: sin respuesta no se agrisa nada.
        if (!cancelado) setDias({});
      });

    return () => {
      cancelado = true;
    };
  }, [desde, hasta, personas]);

  return dias;
}

/** El motivo de ese dia, o null si cabe o si todavia no sabemos. */
export function motivoDe(
  dias: DisponibilidadRango,
  iso: string,
): MotivoNoDisponible | null {
  return dias[iso] ?? null;
}
