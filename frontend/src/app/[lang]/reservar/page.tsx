import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { CheckoutView } from '@/components/checkout-view';
import { getTarifa } from '@/lib/api';
import { getMinBookableDate, parseBookingQuery } from '@/lib/dates';
import { alternativasDe } from '@/lib/site';

export async function generateMetadata({
  params,
}: PageProps<'/[lang]/reservar'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return {
    title: dict.meta.reservar.title,
    description: dict.meta.reservar.description,
    alternates: alternativasDe(lang, '/reservar'),
    // Fuera del indice: es un paso del embudo y con los parametros de fecha
    // generaria infinitas variantes de la misma pagina.
    robots: { index: false, follow: true },
  };
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

  // Sin tarifa del backend no hay precio que mostrar: el checkout se pinta en
  // modo "pagos no disponibles" en vez de inventar una cifra.
  const tarifa = await getTarifa().catch(() => null);

  const parsed = parseBookingQuery(
    (key) => (typeof query[key] === 'string' ? query[key] : undefined),
    minDate,
  );
  const day = parsed.day ?? minDate;
  const time = parsed.time ?? '06:00';
  const people = parsed.people ?? 2;

  return (
    <CheckoutView
      lang={lang}
      dict={dict}
      initialDay={day}
      initialTime={time}
      initialPeople={people}
      minDate={minDate}
      tarifa={tarifa}
    />
  );
}
