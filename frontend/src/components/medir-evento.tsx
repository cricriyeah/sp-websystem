'use client';

import { useEffect } from 'react';
import { medir, type DatosEvento, type EventoVenta } from '@/lib/medicion';

/**
 * Manda un evento de venta al montar la página (ver `lib/medicion.ts`): `ViewContent` en el detalle de un
 * servicio o paquete, `InitiateCheckout` al llegar al checkout. No pinta nada. Va como hoja dentro de páginas
 * de servidor, que no pueden llamar al pixel.
 */
export function MedirEvento({ evento, datos }: { evento: EventoVenta; datos?: DatosEvento }) {
  const clave = `${evento}|${datos?.id ?? ''}`;
  useEffect(() => {
    medir(evento, datos);
    // Una vez por página: los datos llegan del servidor y no cambian mientras se ve.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave]);
  return null;
}
