'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { DateField } from '@/components/date-field';
import { PeopleStepper } from '@/components/people-stepper';
import { TimeField } from '@/components/time-field';

type BookingBarProps = {
  lang: Locale;
  booking: Dictionary['booking'];
  minDate: string;
};

export function BookingBar({ lang, booking, minDate }: BookingBarProps) {
  const router = useRouter();
  const [day, setDay] = useState(minDate);
  const [time, setTime] = useState('06:00');
  const [people, setPeople] = useState(2);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams({ day, time, people: String(people) });
    router.push(`/${lang}/reservar?${params.toString()}`);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-full flex-col gap-2 rounded-3xl bg-surface p-3 shadow-[0_20px_50px_rgba(11,36,32,0.16)] sm:flex-row sm:items-stretch sm:gap-0 sm:divide-x sm:divide-border sm:rounded-full sm:p-3"
    >
      <DateField
        lang={lang}
        label={booking.day}
        value={day}
        onChange={setDay}
        minDate={minDate}
        prevMonthLabel={booking.prevMonth}
        nextMonthLabel={booking.nextMonth}
        personas={people}
        fullLabel={booking.dayFull}
      />

      <TimeField label={booking.time} help={booking.timeHelp} value={time} onChange={setTime} />

      <PeopleStepper
        label={booking.people}
        maxNotice={booking.maxPeopleNotice}
        value={people}
        onChange={setPeople}
      />

      <div className="flex items-center px-1 py-1 sm:pl-3">
        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-full bg-accent px-8 py-4 text-sm font-medium text-accent-foreground transition-transform active:scale-[0.98] sm:w-auto"
        >
          {booking.submit}
          <ArrowRight size={16} weight="bold" />
        </button>
      </div>
    </form>
  );
}
