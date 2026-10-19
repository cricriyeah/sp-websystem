'use client';

import { useCallback, useEffect, useState } from 'react';
import { getCupoRango, type DisponibilidadRango, type MotivoNoDisponible } from '@/lib/api';

type Cargado = { clave: string; dias: DisponibilidadRango; error: boolean };

/**
 * Disponibilidad de un rango de dias, para marcar en el calendario los que ya no
 * admiten al grupo.
 *
 * Depende de `personas` a proposito: un dia puede tener lugares libres y aun asi
 * no recibir a un grupo de 4, porque solo dos pangas de la flota pasan de 3. El
 * dia lleno no es propiedad del dia, cambia con el tamano del grupo.
 *
 * `empresaSlug` es la empresa cuyo cupo se consulta (sin ella, el backend
 * contesta por la empresa por defecto). Si la peticion falla, `dias` queda vacio
 * (nada se marca lleno: el cupo de verdad lo valida el backend al cobrar) y
 * `error` lo dice para que la ruta ofrezca `reintentar`.
 */
export function useDisponibilidad(
  desde: string,
  hasta: string,
  personas: number,
  activo = true,
  empresaSlug?: string,
) {
  // Se guarda junto con la consulta que lo produjo. Asi `cargando` se DERIVA de
  // comparar la clave pedida con la cargada, en vez de ponerse a mano al entrar
  // al efecto: un `setState` al inicio de un efecto provoca un render de mas y
  // React 19 lo marca como error.
  const [intento, setIntento] = useState(0);
  const clave = activo ? `${desde}|${hasta}|${personas}|${empresaSlug ?? ''}|${intento}` : '';
  const [cargado, setCargado] = useState<Cargado | null>(null);

  useEffect(() => {
    if (!activo) return;
    let cancelado = false;
    const esta = `${desde}|${hasta}|${personas}|${empresaSlug ?? ''}|${intento}`;

    getCupoRango(desde, hasta, personas, empresaSlug)
      .then((dias) => {
        if (!cancelado) setCargado({ clave: esta, dias, error: false });
      })
      .catch(() => {
        // Se marca como cargado igual, o el calendario diria «Consultando» para siempre.
        if (!cancelado) setCargado({ clave: esta, dias: {}, error: true });
      });

    return () => {
      cancelado = true;
    };
  }, [desde, hasta, personas, activo, empresaSlug, intento]);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);
  const vigente = cargado?.clave === clave ? cargado : null;

  return {
    dias: vigente?.dias ?? {},
    cargando: activo ? vigente === null : false,
    error: vigente?.error ?? false,
    reintentar,
  };
}

/** El motivo de ese dia, o null si cabe o si todavia no sabemos. */
export function motivoDe(
  dias: DisponibilidadRango,
  iso: string,
): MotivoNoDisponible | null {
  return dias[iso] ?? null;
}
