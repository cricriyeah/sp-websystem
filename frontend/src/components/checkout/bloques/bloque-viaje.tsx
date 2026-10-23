'use client';

import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CalendarioReserva } from '@/components/checkout/calendario-reserva';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { formatDay } from '@/components/checkout/formato-dia';
import { PeopleStepper } from '@/components/people-stepper';
import { TimeField } from '@/components/time-field';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import type { SeleccionFechas } from '@/components/ui/calendario/calendario';
import type { ControlFecha } from '@/lib/control-fecha';
import { fromLocalISODate } from '@/lib/dates';

type Props = {
  lang: Locale;
  checkout: Dictionary['checkout'];
  booking: Dictionary['booking'];
  /** Con el pago en curso el viaje ya no se edita: hora y salida pasan a texto. */
  locked: boolean;
  /** `null` = sin fecha (el cliente la borró): Continuar la pide. */
  day: string | null;
  minDate: string;
  /** Fecha única, o llegada y salida del hospedaje `por_noche`. */
  control: ControlFecha;
  onFechas: (seleccion: SeleccionFechas) => void;
  /** Solo la pesca (`por_recurso_dia`) consulta cupo por día. */
  conCupo: boolean;
  /** Bajo demanda: sin cupo que mostrar, se confirma al pagar. */
  bajoDemanda: boolean;
  empresaSlug?: string;
  errorFecha: string;
  pideHora: boolean;
  time: string;
  horaTexto: string;
  horasDisponibles: string[];
  onHora: (hora: string) => void;
  people: number;
  /** Tope del servicio (`capacidad_maxima`, o 5 sin ella). */
  maxPersonas: number;
  onPersonas: (cantidad: number) => void;
  onTopePersonas: () => void;
  tieneHospedaje: boolean;
  fechaSalida: string | null;
  /** Qué cubre el precio y qué cuesta sumar a alguien, ya en texto (`lib/regla-personas`); cambia con el número. */
  reglaPersonas?: string | null;
};

/**
 * Contenido del paso de viaje del servicio suelto: fecha (o llegada y salida
 * del hospedaje, en el mismo calendario), hora, personas y la nota de personas extra. Sin estado propio: día,
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
  control,
  onFechas,
  conCupo,
  bajoDemanda,
  empresaSlug,
  errorFecha,
  pideHora,
  time,
  horaTexto,
  horasDisponibles,
  onHora,
  people,
  maxPersonas,
  onPersonas,
  onTopePersonas,
  tieneHospedaje,
  fechaSalida,
  reglaPersonas,
}: Props) {
  return (
    <ContenidoViaje
      fecha={
        <>
          <CalendarioReserva
            lang={lang}
            textos={checkout.calendario}
            control={control}
            seleccion={{ desde: day, hasta: tieneHospedaje ? fechaSalida : null }}
            onSeleccion={onFechas}
            minDate={minDate}
            personas={people}
            conCupo={conCupo}
            empresaSlug={empresaSlug}
          />
          {bajoDemanda && <p className="mt-3 texto-pequeno text-apagado">{checkout.calendario.confirmadaAlPagar}</p>}
          {day && (
            <p className="mt-5 border-t border-border pt-5 text-sm text-foreground">
              {formatDay(fromLocalISODate(day), lang)}
              {tieneHospedaje && fechaSalida ? ` → ${formatDay(fromLocalISODate(fechaSalida), lang)}` : ''}
            </p>
          )}
          <ErrorDeCampo id="checkout-error-fecha" mensaje={errorFecha} />
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
          maxNotice={checkout.maxPersonasTope.replace('{max}', String(maxPersonas))}
          value={people}
          maxPeople={maxPersonas}
          onChange={onPersonas}
          disabled={locked}
          onMaxAttempt={onTopePersonas}
        />
      }
      nota={reglaPersonas ? <p aria-live="polite">{reglaPersonas}</p> : undefined}
    />
  );
}
