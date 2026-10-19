'use client';

import { useState } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { Calendario, type SeleccionFechas } from '@/components/ui/calendario/calendario';
import { inicioDeMes, moverMes } from '@/lib/calendario-mes';
import { sumarDias } from '@/lib/calendario-paquete';
import type { ControlFecha } from '@/lib/control-fecha';
import { toLocalISODate } from '@/lib/dates';
import { useDisponibilidad } from '@/lib/disponibilidad';
import { intlLocale } from '@/lib/intl';

type Props = {
  lang: Locale;
  textos: Dictionary['checkout']['calendario'];
  control: ControlFecha;
  seleccion: SeleccionFechas;
  onSeleccion: (seleccion: SeleccionFechas) => void;
  minDate: string;
  noches?: number | null;
  personas: number;
  /**
   * Hay cupo que consultar (`/api/<empresa>/cupo/rango/`). Solo la pesca suelta (`por_recurso_dia`):
   * el endpoint contesta por las pangas de la empresa, así que en hospedaje, bajo demanda, traslados
   * y paquetes no dice nada útil y el cupo se valida al pagar.
   */
  conCupo: boolean;
  empresaSlug?: string;
};

/**
 * `ui/calendario` con el cupo de la ruta: consulta el mes visible y el siguiente (precarga, dentro
 * del tope de 62 días del endpoint) para la empresa del servicio. Mientras carga nada se marca
 * lleno; si falla, el calendario lo dice y ofrece reintentar.
 */
export function CalendarioReserva({
  lang, textos, control, seleccion, onSeleccion, minDate, noches, personas, conCupo, empresaSlug,
}: Props) {
  const hoy = toLocalISODate(new Date());
  const [mes, setMes] = useState(() => inicioDeMes(seleccion.desde ?? minDate));
  const hasta = sumarDias(moverMes(mes, 2), -1);
  const { dias, cargando, error, reintentar } = useDisponibilidad(mes, hasta, personas, conCupo, empresaSlug);

  return (
    <Calendario
      locale={intlLocale(lang)}
      control={control}
      seleccion={seleccion}
      onSeleccion={onSeleccion}
      minDate={minDate}
      hoy={hoy}
      noches={noches}
      sinCupo={dias}
      conCupo={conCupo}
      cargando={cargando}
      errorCupo={error}
      onReintentar={reintentar}
      onMesVisible={setMes}
      enTarjeta
      textos={textos}
    />
  );
}
