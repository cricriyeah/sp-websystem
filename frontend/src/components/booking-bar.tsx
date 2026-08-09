'use client';

import { CalendarBlank, Clock, UsersThree, ArrowRight } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type BookingBarProps = {
  booking: Dictionary['booking'];
  minDate: string;
};

export function BookingBar({ booking, minDate }: BookingBarProps) {
  return (
    <form
      onSubmit={(e) => e.preventDefault()}
      className="flex w-full flex-col gap-2 rounded-3xl bg-surface p-3 shadow-[0_20px_50px_rgba(11,36,32,0.16)] sm:flex-row sm:items-stretch sm:gap-0 sm:divide-x sm:divide-border sm:rounded-full sm:p-3"
    >
      <label className="flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 transition-colors focus-within:bg-background sm:rounded-none">
        <CalendarBlank size={20} className="shrink-0 text-muted" />
        <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
          <span className="text-xs text-muted">{booking.day}</span>
          <input
            type="date"
            min={minDate}
            defaultValue={minDate}
            className="w-full bg-transparent text-sm text-foreground outline-none"
          />
        </span>
      </label>

      <label className="flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 transition-colors focus-within:bg-background sm:rounded-none">
        <Clock size={20} className="shrink-0 text-muted" />
        <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
          <span className="text-xs text-muted">{booking.time}</span>
          <input
            type="time"
            min="05:00"
            max="07:00"
            step={900}
            defaultValue="06:00"
            aria-describedby="booking-time-help"
            className="w-full bg-transparent text-sm text-foreground outline-none"
          />
          <span id="booking-time-help" className="sr-only">
            {booking.timeHelp}
          </span>
        </span>
      </label>

      <label className="flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 transition-colors focus-within:bg-background sm:rounded-none">
        <UsersThree size={20} className="shrink-0 text-muted" />
        <span className="flex flex-1 flex-col items-start gap-0.5 text-left">
          <span className="text-xs text-muted">{booking.people}</span>
          <input
            type="number"
            min={1}
            max={6}
            defaultValue={2}
            className="w-full bg-transparent text-sm text-foreground outline-none"
          />
        </span>
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
