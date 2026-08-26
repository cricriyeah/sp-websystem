'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { useEstadoReserva } from '@/components/booking-state';
import { DateField } from '@/components/date-field';
import { PeopleStepper } from '@/components/people-stepper';
import { TimeField } from '@/components/time-field';

type BookingBarProps = {
  lang: Locale;
  booking: Dictionary['booking'];
  minDate: string;
};

/**
 * La barra de reserva de la portada.
 *
 * **El orden es de dependencia, no de costumbre.** Primero cuantos son, despues
 * el dia, al final la hora. El tamano del grupo decide que dias son siquiera
 * posibles —solo dos de las diez pangas pasan de tres personas— asi que
 * preguntar la fecha antes deja que la respuesta siguiente invalide la anterior.
 *
 * **Las respuestas no son suyas.** Viven en `ProveedorReserva`, asi que la barra
 * de la portada y la que se pega abajo al bajar muestran lo mismo: contestar en
 * una es contestar en las dos.
 *
 * **Arranca vacia, sin valores por defecto.** Un default es una decision tomada
 * por el cliente que el tiene que descubrir y deshacer. El precio de quitarlos es
 * real —pasa de verificar a producir, que cuesta mas— y se paga encadenando las
 * preguntas: contestar una abre la siguiente, asi que el esfuerzo es un toque por
 * respuesta y nunca hay que buscar donde seguir.
 */
export function BookingBar({ lang, booking, minDate }: BookingBarProps) {
  const router = useRouter();

  // Compartido con la barra pegada de abajo cuando las dos viven bajo
  // ProveedorReserva; propio si esta barra anda suelta. Ver booking-state.tsx.
  const { people, day, time, setPeople, setDay, setTime } = useEstadoReserva();

  // Contadores para pedirle apertura a cada panel. Se incrementan al contestar la
  // pregunta anterior, y al intentar enviar con algo sin contestar.
  const [abrirDia, setAbrirDia] = useState(0);
  const [abrirHora, setAbrirHora] = useState(0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Falta algo: en vez de un error, se abre la pregunta sin contestar. El
    // problema queda pegado a su causa y el cliente no tiene que buscar cual es.
    if (people === null || day === null) {
      if (day === null && people !== null) setAbrirDia((n) => n + 1);
      return;
    }
    if (time === null) {
      setAbrirHora((n) => n + 1);
      return;
    }

    const params = new URLSearchParams({ day, time, people: String(people) });
    router.push(`/${lang}/reservar?${params.toString()}`);
  };

  const completo = people !== null && day !== null && time !== null;

  return (
    // Recta y blanca, con sombra: es lo unico del sitio que flota, porque es lo
    // unico que se sale de su seccion para montarse sobre la foto.
    <form
      onSubmit={handleSubmit}
      className="flex w-full flex-col gap-2 bg-background p-3 shadow-[0_18px_44px_rgba(22,23,28,0.16)] sm:flex-row sm:items-stretch sm:gap-0 sm:divide-x sm:divide-border sm:p-3"
    >
      <PeopleStepper
        label={booking.people}
        placeholder={booking.askPeople}
        maxNotice={booking.maxPeopleNotice}
        value={people}
        onChange={(n) => {
          const primeraRespuesta = people === null;
          setPeople(n);
          // Encadenar solo la primera vez: si el cliente esta corrigiendo el
          // numero, abrirle el calendario en la cara seria quitarle el control.
          if (primeraRespuesta && day === null) setAbrirDia((v) => v + 1);
        }}
      />

      <DateField
        lang={lang}
        label={booking.day}
        placeholder={booking.askDay}
        value={day}
        onChange={(d) => {
          const primeraRespuesta = day === null;
          setDay(d);
          if (primeraRespuesta && time === null) setAbrirHora((v) => v + 1);
        }}
        minDate={minDate}
        prevMonthLabel={booking.prevMonth}
        nextMonthLabel={booking.nextMonth}
        // Sin respuesta todavia se consulta para un grupo de 1: es el criterio
        // mas permisivo, asi no se agrisa un dia que quiza si le sirve.
        personas={people ?? 1}
        fullLabel={booking.dayFull}
        solicitarApertura={abrirDia}
      />

      <TimeField
        label={booking.time}
        placeholder={booking.askTime}
        help={booking.timeHelp}
        value={time}
        onChange={setTime}
        solicitarApertura={abrirHora}
      />

      <div className="flex items-center px-1 py-1 sm:pl-3">
        {/* El amarillo es el color de la accion y solo aparece aqui y en la barra
            superior. Sin contestar todo cae a bruma con borde: se sigue pudiendo
            pulsar (abre la pregunta que falta) pero no compite por atencion. */}
        <button
          type="submit"
          className={`flex w-full items-center justify-center gap-2 rounded-full px-8 py-4 text-sm font-semibold whitespace-nowrap transition-all active:scale-[0.98] sm:w-auto ${
            completo
              ? 'bg-action text-action-foreground'
              : 'border border-border-strong bg-surface text-muted'
          }`}
        >
          {booking.submit}
          <ArrowRight size={16} weight="bold" />
        </button>
      </div>
    </form>
  );
}
