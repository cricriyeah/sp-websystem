import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { CheckoutView } from '@/components/checkout-view';
import { getTarifa } from '@/lib/api';
import { getMinBookableDate, MAX_PEOPLE, MIN_PEOPLE, TOUR_HOURS } from '@/lib/dates';

// Precio fijo del tour (no varia por clase de embarcacion, ver
// docs/contexto-negocio.md). Fallback solo si el backend no responde.
const FALLBACK_TOUR_PRICE = 4500;

export async function generateMetadata({
  params,
}: PageProps<'/[lang]/reservar'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return { title: `${dict.checkout.payButton} — ${dict.home.title}` };
}

function clampTime(time: string | undefined, fallback: string) {
  return time && TOUR_HOURS.includes(time) ? time : fallback;
}

function clampPeople(people: string | undefined, fallback: number) {
  const n = Number(people);
  if (!Number.isInteger(n)) return fallback;
  return Math.min(MAX_PEOPLE, Math.max(MIN_PEOPLE, n));
}

export default async function ReservarPage({
  params,
  searchParams,
}: PageProps<'/[lang]/reservar'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;
  const minDate = getMinBookableDate();

  const tourPrice = await getTarifa()
    .then((tarifa) => Number(tarifa.precio))
    .catch(() => FALLBACK_TOUR_PRICE);

  const dayParam = typeof query.day === 'string' ? query.day : undefined;
  const day = dayParam && /^\d{4}-\d{2}-\d{2}$/.test(dayParam) && dayParam >= minDate
    ? dayParam
    : minDate;
  const time = clampTime(typeof query.time === 'string' ? query.time : undefined, '06:00');
  const people = clampPeople(typeof query.people === 'string' ? query.people : undefined, 2);

  return (
    <CheckoutView
      lang={lang}
      dict={dict}
      initialDay={day}
      time={time}
      people={people}
      minDate={minDate}
      tourPrice={tourPrice}
    />
  );
}
