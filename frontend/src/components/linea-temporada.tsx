'use client';

import { useSyncExternalStore } from 'react';

type Props = {
  /** Meses de la temporada, 1 = enero. */
  meses: number[];
  en: string;
  fuera: string;
  /** Lo que se ve sin script y en el HTML del servidor: los meses, sin decir si es hoy. */
  base: string;
  className?: string;
};

const sinSuscripcion = () => () => {};
const mesDeHoy = () => new Date().getMonth() + 1;

/**
 * Una línea que cambia con la fecha del visitante («la ballena ya está en la bahía» o «llega en enero»). La página es
 * estática: el servidor pinta `base` y el navegador la cambia al hidratar, sin efecto ni parpadeo de layout.
 */
export function LineaTemporada({ meses, en, fuera, base, className }: Props) {
  const mes = useSyncExternalStore(sinSuscripcion, mesDeHoy, () => null);
  const texto = mes === null ? base : meses.includes(mes) ? en : fuera;
  return <p className={className}>{texto}</p>;
}
