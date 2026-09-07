import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { CheckoutView } from '@/components/checkout-view';
import { getPaqueteDetalle, getSedes, getTarifa, type PaqueteCatalogo } from '@/lib/api';
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

  const parsed = parseBookingQuery(
    (key) => (typeof query[key] === 'string' ? query[key] : undefined),
    minDate,
  );
  const day = parsed.day ?? minDate;
  const time = parsed.time ?? '06:00';
  const people = parsed.people ?? 2;

  // Si se seleccionó un paquete de experiencias desde el catálogo
  const paqueteSlug = typeof query.paquete === 'string' ? query.paquete : undefined;
  const sedeSlug = typeof query.sede === 'string' ? query.sede : undefined;
  let paquete: PaqueteCatalogo | null = null;

  if (paqueteSlug) {
    if (sedeSlug) {
      paquete = await getPaqueteDetalle(sedeSlug, paqueteSlug).catch(() => null);
    } else {
      const sedes = await getSedes().catch(() => []);
      for (const s of sedes) {
        const p = await getPaqueteDetalle(s.slug, paqueteSlug).catch(() => null);
        if (p) {
          paquete = p;
          break;
        }
      }
    }
  }

  // Resolución de empresa dinámicamente según el ítem seleccionado:
  // - paquete -> paquete.empresa_lider_slug
  // - servicio suelto -> servicio.empresa_slug (query.empresa)
  // - pesca legacy -> NEXT_PUBLIC_EMPRESA_SLUG
  const servicioEmpresa = typeof query.empresa === 'string' ? query.empresa : undefined;
  const paqueteEmpresa = typeof query.paquete_empresa === 'string' ? query.paquete_empresa : undefined;
  const defaultEmpresaSlug = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

  const empresaSlug = paquete?.empresa_lider_slug ?? paqueteEmpresa ?? servicioEmpresa ?? defaultEmpresaSlug;

  // Sin tarifa del backend no hay precio que mostrar: el checkout se pinta en
  // modo "pagos no disponibles" en vez de inventar una cifra.
  const tarifa = await getTarifa(empresaSlug).catch(() => null);

  const excluidosParam = typeof query.excluidos === 'string' ? query.excluidos : undefined;
  const initialServiciosRemovidos = excluidosParam
    ? excluidosParam
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((token) => {
          if (/^\d+$/.test(token) && paquete) {
            const idNum = Number(token);
            const sa = paquete.servicios_asociados.find(
              (item) => (item.servicio?.id ?? item.servicio_id) === idNum,
            );
            return sa?.servicio?.slug ?? token;
          }
          return token;
        })
    : [];

  const fechaSalidaParam =
    typeof query.fecha_salida === 'string'
      ? query.fecha_salida
      : typeof query.salida === 'string'
        ? query.salida
        : undefined;

  // El booking bar siempre manda los tres juntos: si trae alguno explicito es
  // que el cliente acaba de elegir viaje, no que recargo esta misma pagina.
  // Distingue esa llegada de una recuperacion de checkout a medio pagar (ver
  // el comentario largo en CheckoutView).
  const queryOverride = parsed.day !== undefined || parsed.time !== undefined || parsed.people !== undefined;

  return (
    <CheckoutView
      lang={lang}
      dict={dict}
      initialDay={day}
      initialTime={time}
      initialPeople={people}
      minDate={minDate}
      tarifa={tarifa}
      queryOverride={queryOverride}
      empresaSlug={empresaSlug}
      paqueteId={paquete?.id}
      paqueteNombre={paquete?.nombre}
      paquete={paquete}
      initialServiciosRemovidos={initialServiciosRemovidos}
      initialFechaSalida={fechaSalidaParam}
    />
  );
}
