'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CalendarBlank, Clock, UsersThree, ArrowRight, Minus, Plus } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { MAX_PEOPLE, MIN_PEOPLE, TOUR_HOURS } from '@/lib/dates';

type BookingBarProps = {
  lang: Locale;
  booking: Dictionary['booking'];
  minDate: string;
};

function formatHour(time: string) {
  const [h, m] = time.split(':').map(Number);
  const period = h >= 12 ? 'pm' : 'am';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, '0')} ${period}`;
}

export function BookingBar({ lang, booking, minDate }: BookingBarProps) {
  const router = useRouter();
  const [day, setDay] = useState(minDate);
  const [time, setTime] = useState('06:00');
  const [people, setPeople] = useState(2);
  const [showMaxNotice, setShowMaxNotice] = useState(false);
  const noticeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
  }, []);

  const adjustPeople = (delta: number) => {
    setPeople((prev) => {
      const next = prev + delta;
      if (next > MAX_PEOPLE) {
        setShowMaxNotice(true);
        if (noticeTimeout.current) clearTimeout(noticeTimeout.current);
        noticeTimeout.current = setTimeout(() => setShowMaxNotice(false), 2500);
        return MAX_PEOPLE;
      }
      return Math.min(MAX_PEOPLE, Math.max(MIN_PEOPLE, next));
    });
  };

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
      <label className="flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 transition-colors focus-within:bg-background sm:rounded-none">
        <CalendarBlank size={20} className="shrink-0 text-muted" />
        <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
          <span className="text-xs text-muted">{booking.day}</span>
          <input
            type="date"
            min={minDate}
            value={day}
            onChange={(e) => setDay(e.target.value < minDate ? minDate : e.target.value)}
            className="w-full bg-transparent text-sm text-foreground outline-none"
          />
        </span>
      </label>

      <label className="flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 transition-colors focus-within:bg-background sm:rounded-none">
        <Clock size={20} className="shrink-0 text-muted" />
        <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
          <span className="text-xs text-muted">{booking.time}</span>
          <select
            value={time}
            onChange={(e) => setTime(e.target.value)}
            aria-describedby="booking-time-help"
            className="w-full bg-transparent text-sm text-foreground outline-none"
          >
            {TOUR_HOURS.map((h) => (
              <option key={h} value={h}>
                {formatHour(h)}
              </option>
            ))}
          </select>
          <span id="booking-time-help" className="sr-only">
            {booking.timeHelp}
          </span>
        </span>
      </label>

      <label className="relative flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 transition-colors focus-within:bg-background sm:rounded-none">
        <UsersThree size={20} className="shrink-0 text-muted" />
        <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
          <span className="text-xs text-muted">{booking.people}</span>
          <span className="flex w-full items-center justify-between">
            <span className="text-sm text-foreground">{people}</span>
            <span className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => adjustPeople(-1)}
                disabled={people <= MIN_PEOPLE}
                aria-label="-"
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border disabled:opacity-30"
              >
                <Minus size={12} />
              </button>
              <button
                type="button"
                onClick={() => adjustPeople(1)}
                aria-label="+"
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-border"
              >
                <Plus size={12} />
              </button>
            </span>
          </span>
        </span>

        {showMaxNotice && (
          <span className="absolute -bottom-8 left-0 z-10 rounded-lg bg-foreground px-3 py-1.5 text-xs whitespace-nowrap text-surface shadow-lg">
            {booking.maxPeopleNotice}
          </span>
        )}
      </label>

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
