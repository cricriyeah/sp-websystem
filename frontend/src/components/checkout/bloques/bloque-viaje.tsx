'use client';

import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutCalendar } from '@/components/checkout-calendar';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { formatDay } from '@/components/checkout/formato-dia';
import { DateField } from '@/components/date-field';
import { PeopleStepper } from '@/components/people-stepper';
import { TimeField } from '@/components/time-field';
import { fromLocalISODate } from '@/lib/dates';

type Props = {
  lang: Locale;
  checkout: Dictionary['checkout'];
  booking: Dictionary['booking'];
  /** Con el pago en curso el viaje ya no se edita: hora y salida pasan a texto. */
  locked: boolean;
  day: string;
  minDate: string;
  onDia: (isoDate: string) => void;
  pideHora: boolean;
  time: string;
  horaTexto: string;
  horasDisponibles: string[];
  onHora: (hora: string) => void;
  people: number;
  onPersonas: (cantidad: number) => void;
  onTopePersonas: () => void;
  tieneHospedaje: boolean;
  fechaSalida: string;
  fechaSalidaMinima: string;
  onFechaSalida: (isoDate: string) => void;
  personasIncluidas: number;
  precioPersonaExtra: number;
  currency: Intl.NumberFormat;
};

/**
 * Contenido del paso de viaje del servicio suelto: fecha, hora, personas,
 * salida (hospedaje) y la nota de personas extra. Sin estado propio: día,
 * hora, personas y salida viven en `CheckoutView` (cupo, precio, reserva y
 * recuperación los leen), así que plegar la tarjeta no pierde nada.
 */
export function BloqueViaje({
  lang,
  checkout,
  booking,
  locked,
  day,
  minDate,
  onDia,
  pideHora,
  time,
  horaTexto,
  horasDisponibles,
  onHora,
  people,
  onPersonas,
  onTopePersonas,
  tieneHospedaje,
  fechaSalida,
  fechaSalidaMinima,
  onFechaSalida,
  personasIncluidas,
  precioPersonaExtra,
  currency,
}: Props) {
  return (
    <ContenidoViaje
      fecha={
        <>
          <CheckoutCalendar
            lang={lang}
            selected={day}
            onSelect={onDia}
            minDate={minDate}
            personas={people}
            fullLabel={checkout.dayFull}
            weekdaysShort={checkout.weekdaysShort}
          />
          <p className="mt-5 border-t border-border pt-5 text-sm text-foreground">
            {formatDay(fromLocalISODate(day), lang)}
          </p>
        </>
      }
      hora={pideHora ? (locked ? (
        <p className="px-6 py-4 text-sm text-muted">
          {checkout.hourLabel}: <span className="text-foreground">{horaTexto}</span>
        </p>
      ) : (
        <TimeField
          label={checkout.hourLabel}
          help={booking.timeHelp}
          value={time}
          onChange={onHora}
          availableHours={horasDisponibles}
        />
      )) : undefined}
      personas={
        <PeopleStepper
          label={checkout.peopleLabel}
          maxNotice={booking.maxPeopleNotice}
          value={people}
          onChange={onPersonas}
          disabled={locked}
          onMaxAttempt={onTopePersonas}
        />
      }
      salida={tieneHospedaje ? (locked ? (
        <p className="text-sm text-foreground">
          {checkout.checkoutDateLabel}: {formatDay(fromLocalISODate(fechaSalida), lang)}
        </p>
      ) : (
        <div className="border border-border bg-superficie">
          <DateField
            lang={lang}
            label={checkout.checkoutDateLabel}
            value={fechaSalida}
            onChange={onFechaSalida}
            minDate={fechaSalidaMinima}
            prevMonthLabel={booking.prevMonth}
            nextMonthLabel={booking.nextMonth}
            personas={people}
            fullLabel={checkout.dayFull}
            sinCupo
          />
        </div>
      )) : undefined}
      nota={precioPersonaExtra > 0 ? (
        <p>
          {checkout.extraPeopleHint
            .replace('{included}', String(personasIncluidas))
            .replace('{price}', currency.format(precioPersonaExtra))}
        </p>
      ) : undefined}
    />
  );
}
