'use client';

import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BloqueDePaso } from '@/components/checkout-section-card';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { Despliegue } from '@/components/ui/despliegue';
import { TipoTrasladoCards } from '@/components/checkout/tipo-traslado-cards';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import { PeopleStepper } from '@/components/people-stepper';
import { FechaPaquete, FechaRegresoCompacta } from '@/components/pedido/fecha-paquete';
import { TimeField } from '@/components/time-field';
import type { TipoTraslado } from '@/lib/api';

type Props = {
  lang: Locale;
  traslados: Dictionary['traslados'];
  checkout: Dictionary['checkout'];
  pedido: Dictionary['pedido'];
  booking: Dictionary['booking'];
  tiposDisponibles: TipoTraslado[];
  tipoTraslado: TipoTraslado;
  getPrecioDesde: (tipo: TipoTraslado) => string | null;
  /** Cambia el tipo y ajusta la fecha de regreso (solo `redondo_aeropuerto` la tiene). */
  onTipo: (tipo: TipoTraslado) => void;
  fecha: string;
  minDate: string;
  /** Cambia la fecha y empuja el regreso si quedó antes o igual. */
  onFecha: (fecha: string) => void;
  fechaRegreso: string | null;
  minFechaRegreso: string;
  onFechaRegreso: (fecha: string) => void;
  hora: string;
  horasDisponibles: string[];
  onHora: (hora: string) => void;
  personas: number;
  maxCapacidad: number;
  onPersonas: (cantidad: number) => void;
  onTopePersonas: () => void;
  /** Error de la tarjeta de viaje (fechas). */
  error: string;
};

/**
 * Contenido del paso de viaje de traslados: tipo → fecha (con el regreso
 * pegado a ella, solo con "redondo con aeropuerto") → hora y pasajeros → nota.
 * Sin estado propio: tipo, fechas, hora y pasajeros viven en `TrasladoView`
 * (tarifa, payload y recuperación los leen), así que plegar la tarjeta no pierde
 * nada.
 */
export function BloqueViajeTraslado({
  lang,
  traslados,
  checkout,
  pedido,
  booking,
  tiposDisponibles,
  tipoTraslado,
  getPrecioDesde,
  onTipo,
  fecha,
  minDate,
  onFecha,
  fechaRegreso,
  minFechaRegreso,
  onFechaRegreso,
  hora,
  horasDisponibles,
  onHora,
  personas,
  maxCapacidad,
  onPersonas,
  onTopePersonas,
  error,
}: Props) {
  return (
    <>
      {/* Lo que define el producto va primero. */}
      <BloqueDePaso titulo={traslados.step1Title}>
        <TipoTrasladoCards
          tipos={tiposDisponibles}
          valor={tipoTraslado}
          textos={traslados.types}
          etiqueta={traslados.step1Title}
          precioDesde={getPrecioDesde}
          onChange={onTipo}
        />
      </BloqueDePaso>

      <ContenidoViaje
        fecha={
          <>
            <FechaPaquete
              lang={lang}
              label={traslados.fields.fecha}
              value={fecha}
              onChange={onFecha}
              minDate={minDate}
              chooseLabel={pedido.chooseStart}
              viewMonthLabel={pedido.viewMonth}
              hideMonthLabel={pedido.hideMonth}
              previousWeekLabel={pedido.previousWeek}
              nextWeekLabel={pedido.nextWeek}
              previousMonthLabel={booking.prevMonth}
              nextMonthLabel={booking.nextMonth}
              personas={personas}
              fullLabel={checkout.dayFull}
            />
            {/* El regreso depende del tipo y de la fecha de inicio: aparece
                pegado a la fecha, y solo con "redondo con aeropuerto". */}
            <Despliegue abierto={tipoTraslado === 'redondo_aeropuerto'}>
              <div className="pt-5">
                <FechaRegresoCompacta
                  lang={lang}
                  label={traslados.fields.fechaRegreso}
                  value={fechaRegreso}
                  onChange={onFechaRegreso}
                  minDate={minFechaRegreso}
                  chooseLabel={pedido.chooseReturnDate}
                  changeButtonLabel={checkout.changeStep}
                  doneButtonLabel={checkout.doneEditing}
                  viewMonthLabel={pedido.viewMonth}
                  hideMonthLabel={pedido.hideMonth}
                  previousWeekLabel={pedido.previousWeek}
                  nextWeekLabel={pedido.nextWeek}
                  previousMonthLabel={booking.prevMonth}
                  nextMonthLabel={booking.nextMonth}
                  personas={personas}
                  fullLabel={checkout.dayFull}
                />
              </div>
            </Despliegue>
          </>
        }
        hora={
          <TimeField
            label={traslados.fields.hora}
            help={checkout.hourLabel}
            value={hora}
            onChange={onHora}
            availableHours={horasDisponibles}
          />
        }
        personas={
          <PeopleStepper
            label={traslados.fields.pasajeros}
            value={personas}
            onChange={onPersonas}
            maxPeople={maxCapacidad}
            minPeople={1}
            maxNotice={traslados.fields.maxPasajerosNotice.replace('{max}', String(maxCapacidad))}
            onMaxAttempt={onTopePersonas}
          />
        }
        nota={
          <p>
            <span className="font-semibold text-foreground">{traslados.summary.transfer}</span>
            {' '}
            {traslados.summary.included}
          </p>
        }
      />
      <ErrorDeCampo id="error-viaje" mensaje={error} />
    </>
  );
}
