import type { Dispatch } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { ContenidoViaje } from '@/components/checkout/contenido-viaje';
import { ErrorDeCampo } from '@/components/field-error';
import { PeopleStepper } from '@/components/people-stepper';
import { TimeField } from '@/components/time-field';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { horasDePaquete } from '@/lib/horario-servicio';
import type { AccionPedido } from '@/lib/pedido-estado';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { FechaPaquete } from './fecha-paquete';

type Props = {
  lang: Locale;
  dict: Dictionary;
  paquete: PaqueteCatalogo;
  minDate: string;
  inicio: string | null;
  hora: string;
  moneda: Moneda;
  personasPaquete: number;
  maxPersonas: number | null;
  slugPrincipal: string | undefined;
  noches: number | null;
  salida: string | null;
  anclaMostrada: string;
  extra: number | null;
  precioPersonas: string;
  formatearFecha: (iso: string) => string;
  errorViaje: string;
  despachar: Dispatch<AccionPedido>;
  onTopePersonas: () => void;
};

/**
 * Contenido de la tarjeta "Viaje" del paquete: fecha de inicio, hora (si el
 * paquete la pide), personas (si el precio depende de ellas) y la nota de
 * noches y precio. Sin estado propio: inicio, hora y personas viven en el
 * reducer del pedido, así que plegar la tarjeta no pierde nada. Devuelve un
 * fragmento: el contenido y el error son hijos directos de la tarjeta.
 */
export function BloqueViajePaquete({
  lang, dict, paquete, minDate, inicio, hora, moneda, personasPaquete, maxPersonas, slugPrincipal, noches, salida,
  anclaMostrada, extra, precioPersonas, formatearFecha, errorViaje, despachar, onTopePersonas,
}: Props) {
  const { checkout, booking, pedido: textos } = dict;
  return (
    <>
      <ContenidoViaje
        fecha={
          <FechaPaquete
            lang={lang}
            label={textos.startLabel}
            value={inicio}
            onChange={(valor) => despachar({ tipo: 'inicio', valor })}
            minDate={minDate}
            chooseLabel={textos.chooseStart}
            viewMonthLabel={textos.viewMonth}
            hideMonthLabel={textos.hideMonth}
            previousWeekLabel={textos.previousWeek}
            nextWeekLabel={textos.nextWeek}
            previousMonthLabel={booking.prevMonth}
            nextMonthLabel={booking.nextMonth}
            personas={personasPaquete}
            fullLabel={checkout.dayFull}
          />
        }
        hora={paquete.pide_hora ? (
          <TimeField
            label={checkout.hourLabel}
            help={booking.timeHelp}
            value={hora}
            availableHours={horasDePaquete(paquete)}
            onChange={(valor) => despachar({ tipo: 'hora', valor })}
          />
        ) : undefined}
        personas={paquete.precio_depende_de_personas && maxPersonas !== null ? (
          <PeopleStepper
            label={textos.peopleQuestion}
            maxNotice={textos.maxPeoplePackage.replace('{max}', String(maxPersonas))}
            value={personasPaquete}
            maxPeople={maxPersonas}
            minPeople={1}
            onChange={(valor) => {
              if (slugPrincipal) despachar({ tipo: 'personasPaquete', slugPrincipal, valor });
            }}
            onMaxAttempt={() => onTopePersonas()}
          />
        ) : undefined}
        nota={
          <>
            {noches !== null && salida && (
              <p>{textos.nightsNote.replace('{n}', String(noches)).replace('{fecha}', formatearFecha(salida))}</p>
            )}
            {paquete.precio_depende_de_personas && (
              <>
                <p className="font-medium text-foreground">
                  {anclaMostrada} {moneda}{' '}
                  {paquete.estrategia_precio === 'por_persona'
                    ? textos.perPerson
                    : textos.perGroup.replace('{n}', String(paquete.personas_precio_base))}
                </p>
                {paquete.estrategia_precio === 'por_grupo' && extra !== null && (
                  <p>{textos.extraPerson.replace('{precio}', formatearPrecio(extra, moneda))}</p>
                )}
                <p>{precioPersonas}</p>
              </>
            )}
          </>
        }
      />
      <ErrorDeCampo id="pedido-viaje-error" mensaje={errorViaje} />
    </>
  );
}
