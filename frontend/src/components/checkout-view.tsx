'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Fish, MapPin, Warning } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutCalendar } from '@/components/checkout-calendar';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { StripePanel } from '@/components/stripe-panel';
import { ApiError, crearPago, crearReserva, getCupo, type Pago } from '@/lib/api';
import { toLocalISODate } from '@/lib/dates';

const CUPO_SEARCH_LIMIT_DAYS = 90;

function addDays(isoDate: string, days: number) {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + days);
  return toLocalISODate(date);
}

type CheckoutViewProps = {
  lang: Locale;
  dict: Dictionary;
  initialDay: string;
  time: string;
  people: number;
  minDate: string;
  tourPrice: number;
};

// Espejo de backend/apps/payments/pricing.py (AMENITY_PRICE) — solo para
// mostrar el desglose en la UI; el monto que se cobra siempre lo calcula
// el servidor al crear el PaymentIntent.
const AMENITY_PRICE = { drinks: 150, lunch: 300, transport: 250 };

type Phase = 'form' | 'submitting' | 'payment' | 'unavailable' | 'error';

function formatDay(date: Date, lang: Locale) {
  const weekday = new Intl.DateTimeFormat(lang, { weekday: 'long' }).format(date);
  const month = new Intl.DateTimeFormat(lang, { month: 'long' }).format(date);
  const day = String(date.getDate()).padStart(2, '0');
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  return lang === 'es'
    ? `${cap(weekday)} ${day} de ${cap(month)}`
    : `${cap(weekday)}, ${cap(month)} ${day}`;
}

function formatHour(time: string) {
  const [h, m] = time.split(':').map(Number);
  const period = h >= 12 ? 'pm' : 'am';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, '0')} ${period}`;
}

export function CheckoutView({ lang, dict, initialDay, time, people, minDate, tourPrice }: CheckoutViewProps) {
  const { checkout, nav, footer } = dict;
  const [day, setDay] = useState(initialDay);
  const [amenities, setAmenities] = useState({ drinks: false, lunch: false, transport: false });
  const [formaPago, setFormaPago] = useState<'completo' | 'anticipo'>('completo');
  const [contact, setContact] = useState({ phone: '', fullName: '', email: '' });
  const [phase, setPhase] = useState<Phase>('form');
  const [error, setError] = useState('');
  const [pago, setPago] = useState<Pago | null>(null);
  const [dayFullNotice, setDayFullNotice] = useState<string | null>(null);
  const cupoCheckId = useRef(0);

  // El cupo real se valida en el backend (al pagar), esto solo es feedback
  // adelantado: si el dia elegido ya esta lleno, reasigna automaticamente al
  // dia mas proximo con espacio y avisa. Nunca bloquea el flujo (ver
  // docs/contexto-negocio.md — el checkout no debe poner trabas).
  useEffect(() => {
    const checkId = ++cupoCheckId.current;

    (async () => {
      let candidate = day;
      for (let i = 0; i < CUPO_SEARCH_LIMIT_DAYS; i++) {
        let disponible: boolean;
        try {
          disponible = (await getCupo(candidate)).disponible;
        } catch {
          return;
        }
        if (cupoCheckId.current !== checkId) return;

        if (disponible) {
          if (candidate !== day) {
            setDay(candidate);
            setDayFullNotice(
              checkout.dayFullNotice.replace('{date}', formatDay(new Date(`${candidate}T00:00:00`), lang))
            );
          }
          return;
        }
        candidate = addDays(candidate, 1);
      }
    })();
  }, [day, lang, checkout.dayFullNotice]);

  const currency = useMemo(
    () => new Intl.NumberFormat(lang, { style: 'currency', currency: 'MXN' }),
    [lang]
  );

  const lines = [
    { label: checkout.tourLabel, amount: currency.format(tourPrice) },
    ...(
      Object.keys(amenities) as Array<keyof typeof amenities>
    )
      .filter((key) => amenities[key])
      .map((key) => ({
        label: checkout.amenities[key],
        amount: currency.format(AMENITY_PRICE[key]),
      })),
  ];
  const total = tourPrice + Object.keys(amenities).reduce(
    (sum, key) => sum + (amenities[key as keyof typeof amenities] ? AMENITY_PRICE[key as keyof typeof amenities] : 0),
    0
  );
  const amountDueNow = formaPago === 'completo' ? total : Math.round(total * 0.3 * 100) / 100;

  const peopleUnit = people === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other;
  const dayDate = useMemo(() => new Date(`${day}T00:00:00`), [day]);

  const handleSubmit = async () => {
    if (!contact.phone.trim() || !contact.fullName.trim() || !contact.email.trim()) {
      setError(checkout.missingFields);
      setPhase('error');
      return;
    }

    setPhase('submitting');
    setError('');

    try {
      const reserva = await crearReserva({
        fecha: day,
        hora: time,
        numero_personas: people,
        nombre_cliente: contact.fullName,
        telefono_cliente: contact.phone,
        correo_cliente: contact.email,
      });

      const selectedAmenities = (Object.keys(amenities) as Array<keyof typeof amenities>).filter(
        (key) => amenities[key]
      );

      const pagoResponse = await crearPago(reserva.id, {
        amenities: selectedAmenities,
        forma_pago: formaPago,
      });

      setPago(pagoResponse);
      setPhase('payment');
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setPhase('unavailable');
        return;
      }
      setError(checkout.errorGeneric);
      setPhase('error');
    }
  };

  return (
    <div className="min-h-dvh bg-background">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 sm:px-8 lg:px-12">
        <Link
          href={`/${lang}`}
          className="flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {checkout.back}
        </Link>

        <Link href={`/${lang}`} className="flex items-center gap-2 text-foreground">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-foreground text-surface">
            <Fish size={16} weight="fill" />
          </span>
          <span className="hidden text-sm font-medium tracking-tight sm:inline">
            {nav.brandMain} <span className="italic font-light">{nav.brandAccent}</span>
          </span>
        </Link>
      </header>

      {dayFullNotice && (
        <div className="mx-auto mb-2 flex max-w-6xl items-start gap-3 px-6 sm:px-8 lg:px-12">
          <div className="flex w-full items-start gap-3 rounded-2xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-foreground">
            <Warning size={18} className="mt-0.5 shrink-0 text-accent" />
            <p>{dayFullNotice}</p>
          </div>
        </div>
      )}

      <main className="mx-auto grid max-w-6xl gap-10 px-6 pb-24 sm:px-8 lg:grid-cols-2 lg:items-start lg:gap-16 lg:px-12">
        <div className="flex flex-col gap-6">
          <CheckoutSectionCard step={1} title={checkout.tripHeadline}>
            <CheckoutCalendar
              lang={lang}
              selected={day}
              onSelect={setDay}
              minDate={minDate}
              weekdaysShort={checkout.weekdaysShort}
            />

            <dl className="mt-6 flex flex-col gap-2 border-t border-border pt-5 text-sm">
              <div className="flex gap-2">
                <dt className="text-muted">{checkout.dayLabel}:</dt>
                <dd className="text-foreground">{formatDay(dayDate, lang)}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-muted">{checkout.hourLabel}:</dt>
                <dd className="text-foreground">{formatHour(time)}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-muted">{checkout.peopleLabel}:</dt>
                <dd className="text-foreground">
                  {people} {peopleUnit}
                </dd>
              </div>
            </dl>
          </CheckoutSectionCard>

          <CheckoutSectionCard step={2} title={checkout.contactHeadline}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-sm sm:col-span-1">
                <span className="text-muted">{checkout.phone}</span>
                <input
                  type="tel"
                  required
                  disabled={phase === 'payment'}
                  value={contact.phone}
                  onChange={(e) => setContact((prev) => ({ ...prev, phone: e.target.value }))}
                  className="rounded-xl border border-border bg-background px-4 py-3 text-foreground outline-none focus:border-accent disabled:opacity-60"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-sm sm:col-span-1">
                <span className="text-muted">{checkout.fullName}</span>
                <input
                  type="text"
                  required
                  disabled={phase === 'payment'}
                  value={contact.fullName}
                  onChange={(e) => setContact((prev) => ({ ...prev, fullName: e.target.value }))}
                  className="rounded-xl border border-border bg-background px-4 py-3 text-foreground outline-none focus:border-accent disabled:opacity-60"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-sm sm:col-span-2">
                <span className="text-muted">{checkout.email}</span>
                <input
                  type="email"
                  required
                  disabled={phase === 'payment'}
                  value={contact.email}
                  onChange={(e) => setContact((prev) => ({ ...prev, email: e.target.value }))}
                  className="rounded-xl border border-border bg-background px-4 py-3 text-foreground outline-none focus:border-accent disabled:opacity-60"
                />
              </label>
            </div>
          </CheckoutSectionCard>

          <CheckoutSectionCard step={3} title={checkout.meetingPointLabel}>
            <div className="flex gap-3 text-sm">
              <MapPin size={20} className="mt-0.5 shrink-0 text-accent" />
              <div>
                <p className="text-foreground">{footer.address}</p>
                <p className="text-foreground">{footer.city}</p>
              </div>
            </div>

            <p className="mt-5 max-w-[60ch] border-t border-border pt-5 text-sm leading-relaxed text-muted">
              {checkout.notice}
            </p>
          </CheckoutSectionCard>

          <CheckoutSectionCard step={4} title={checkout.amenitiesHeadline}>
            <div className="flex flex-col gap-3">
              {(Object.keys(amenities) as Array<keyof typeof amenities>).map((key) => (
                <label
                  key={key}
                  className="flex items-start gap-3 rounded-xl border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-background"
                >
                  <input
                    type="checkbox"
                    checked={amenities[key]}
                    disabled={phase === 'payment'}
                    onChange={(e) =>
                      setAmenities((prev) => ({ ...prev, [key]: e.target.checked }))
                    }
                    className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                  />
                  <span>{checkout.amenities[key]}</span>
                </label>
              ))}
            </div>
          </CheckoutSectionCard>
        </div>

        <div className="lg:sticky lg:top-10 lg:self-start">
          <StripePanel
            checkout={checkout}
            lines={lines}
            total={currency.format(total)}
            amountDueNow={currency.format(amountDueNow)}
            formaPago={formaPago}
            onFormaPagoChange={setFormaPago}
            phase={phase}
            error={error}
            pago={pago}
            onSubmit={handleSubmit}
          />
        </div>
      </main>
    </div>
  );
}
