'use client';

import { useState } from 'react';
import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import { toLocalISODate } from '@/lib/dates';

type CheckoutCalendarProps = {
  lang: Locale;
  selected: string;
  onSelect: (isoDate: string) => void;
  minDate: string;
  weekdaysShort: string[];
};

const toIso = toLocalISODate;

function startOfWeek(date: Date) {
  const start = new Date(date);
  const day = (start.getDay() + 6) % 7; // 0 = Monday
  start.setDate(start.getDate() - day);
  return start;
}

export function CheckoutCalendar({
  lang,
  selected,
  onSelect,
  minDate,
  weekdaysShort,
}: CheckoutCalendarProps) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date(selected)));

  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(weekStart);
    date.setDate(date.getDate() + i);
    return date;
  });

  const monthLabel = new Intl.DateTimeFormat(lang, { month: 'long', year: 'numeric' }).format(
    days[0]
  );
  const capitalizedMonth = monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);

  const shiftWeek = (delta: number) => {
    const next = new Date(weekStart);
    next.setDate(next.getDate() + delta * 7);
    setWeekStart(next);
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => shiftWeek(-1)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground"
        >
          <CaretLeft size={16} />
        </button>
        <p className="text-sm font-medium text-foreground">{capitalizedMonth}</p>
        <button
          type="button"
          onClick={() => shiftWeek(1)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-background hover:text-foreground"
        >
          <CaretRight size={16} />
        </button>
      </div>

      <div className="mt-4 grid grid-cols-7 gap-2">
        {days.map((date, i) => {
          const iso = toIso(date);
          const isSelected = iso === selected;
          const isDisabled = iso < minDate;

          return (
            <button
              key={iso}
              type="button"
              disabled={isDisabled}
              onClick={() => onSelect(iso)}
              className={`flex flex-col items-center gap-1 rounded-xl border px-1 py-2.5 text-xs transition-colors ${
                isSelected
                  ? 'border-accent bg-accent text-accent-foreground'
                  : isDisabled
                    ? 'cursor-not-allowed border-border text-muted/40'
                    : 'border-border text-foreground hover:border-accent/50'
              }`}
            >
              <span className="text-[11px] opacity-80">{weekdaysShort[i]}</span>
              <span className="font-medium">{date.getDate()}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
