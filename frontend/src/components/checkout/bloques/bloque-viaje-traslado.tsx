'use client';

import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BloqueDePaso } from '@/components/checkout-section-card';
import { CalendarioReserva } from '@/components/checkout/calendario-reserva';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { formatDay } from '@/components/checkout/formato-dia';
import { TipoTrasladoCards } from '@/components/checkout/tipo-traslado-cards';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import type { SeleccionFechas } from '@/components/ui/calendario/calendario';
import { PeopleStepper } from '@/components/people-stepper';
import { TimeField } from '@/components/time-field';
import type { TipoTraslado } from '@/lib/api';
import { controlDeFecha } from '@/lib/control-fecha';
import { fromLocalISODate } from '@/lib/dates';

type Props = {
  lang: Locale;
  traslados: Dictionary['traslados'];
  checkout: Dictionary['checkout'];
  pedido: Dictionary['pedido'];
  tiposDisponibles: TipoTraslado[];
  tipoTraslado: TipoTraslado;
  getPrecioDesde: (tipo: TipoTraslado) => string | null;
  /** Cambia el tipo y ajusta la fecha de regreso (solo `redondo_aeropuerto` la tiene). */
  onTipo: (tipo: TipoTraslado) => void;
  /** `null` = sin fecha (el cliente la borró): Continuar la pide. */
  fecha: string | null;
  minDate: string;
  fechaRegreso: string | null;
  /** Ida (y regreso, solo con «redondo con aeropuerto»), del mismo calendario. */
  onFechas: (seleccion: SeleccionFechas) => void;
  hora: string;
  horasDisponibles: string[];
  onHora: (hora: string) => void;
  personas: number;
  maxCapacidad: number;
  onPersonas: (cantidad: number) => void;
  onTopePersonas: () => void;
  /** Error de la tarjeta de viaje (fechas). */
  error: string;
  /**
   * Solo una parte, para las pantallas del asistente móvil (tipo · fecha · hora y pasajeros).
   * Sin ella, las tres en orden (la tarjeta de escritorio).
   */
  parte?: 'tipo' | 'fecha' | 'hora-pasajeros';
};

/**
 * Contenido del paso de viaje de traslados: tipo → fecha (un solo calendario de
 * ida y regreso con "redondo con aeropuerto") → hora y pasajeros → nota.
 * Sin estado propio: tipo, fechas, hora y pasajeros viven en `TrasladoView`
 * (tarifa, payload y recuperación los leen), así que plegar la tarjeta no pierde
 * nada.
 */
export function BloqueViajeTraslado({
  lang,
  traslados,
  checkout,
  pedido,
  tiposDisponibles,
  tipoTraslado,
  getPrecioDesde,
  onTipo,
  fecha,
  minDate,
  fechaRegreso,
  onFechas,
  hora,
  horasDisponibles,
  onHora,
  personas,
  maxCapacidad,
  onPersonas,
  onTopePersonas,
  error,
  parte,
}: Props) {
  const tipo = (
    <TipoTrasladoCards
      tipos={tiposDisponibles}
      valor={tipoTraslado}
      textos={traslados.types}
      etiqueta={traslados.step1Title}
      precioDesde={getPrecioDesde}
      onChange={onTipo}
    />
  );
  const conRegreso = tipoTraslado === 'redondo_aeropuerto';
  const { control } = controlDeFecha({ tipo: 'traslado', tipoTraslado });
  const fechas = (
    <div>
      <p className="mb-3 text-sm font-medium text-foreground">{traslados.fields.fecha}</p>
      <CalendarioReserva
        lang={lang}
        textos={checkout.calendario}
        control={control}
        seleccion={{ desde: fecha, hasta: conRegreso ? fechaRegreso : null }}
        onSeleccion={onFechas}
        minDate={minDate}
        personas={personas}
        conCupo={false}
      />
      {/* Con ida y regreso, las dos fechas se leen por separado: el regreso es obligatorio. */}
      {fecha && (
        <dl className="mt-5 flex flex-col gap-1 border-t border-border pt-5 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-apagado">{traslados.fields.fecha}</dt>
            <dd className="text-foreground first-letter:capitalize">{formatDay(fromLocalISODate(fecha), lang)}</dd>
          </div>
          {conRegreso && (
            <div className="flex justify-between gap-3">
              <dt className="text-apagado">{traslados.fields.fechaRegreso}</dt>
              <dd className="text-foreground first-letter:capitalize">
                {fechaRegreso ? formatDay(fromLocalISODate(fechaRegreso), lang) : pedido.chooseReturnDate}
              </dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
  const horaCampo = (
    <TimeField
      label={traslados.fields.hora}
      help={checkout.hourLabel}
      value={hora}
      onChange={onHora}
      availableHours={horasDisponibles}
    />
  );
  const personasCampo = (
    <PeopleStepper
      label={traslados.fields.pasajeros}
      value={personas}
      onChange={onPersonas}
      maxPeople={maxCapacidad}
      minPeople={1}
      maxNotice={checkout.maxPersonasTope.replace('{max}', String(maxCapacidad))}
      onMaxAttempt={onTopePersonas}
    />
  );
  const nota = (
    <p>
      <span className="font-semibold text-foreground">{traslados.summary.transfer}</span>
      {' '}
      {traslados.summary.included}
    </p>
  );
  const errorViaje = <ErrorDeCampo id="error-viaje" mensaje={error} />;

  if (parte === 'tipo') return tipo;
  if (parte === 'fecha') return <>{fechas}{errorViaje}</>;
  if (parte === 'hora-pasajeros') return <ContenidoViaje fecha={null} hora={horaCampo} personas={personasCampo} nota={nota} />;

  return (
    <>
      {/* Lo que define el producto va primero. */}
      <BloqueDePaso titulo={traslados.step1Title}>{tipo}</BloqueDePaso>
      <ContenidoViaje fecha={fechas} hora={horaCampo} personas={personasCampo} nota={nota} />
      {errorViaje}
    </>
  );
}
