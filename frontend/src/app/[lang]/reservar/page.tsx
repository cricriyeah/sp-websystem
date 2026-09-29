import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { CheckoutView } from '@/components/checkout-view';
import { PedidoPaquete } from '@/components/pedido/pedido-paquete';
import { getPaqueteDetalle, getServicioDetalle, getTraslados, type PaqueteCatalogo, type ServicioCatalogo, type TrasladosCatalogo } from '@/lib/api';
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
    if (!sedeSlug) notFound();
    paquete = await getPaqueteDetalle(sedeSlug, paqueteSlug).catch(() => null);
  }

  if (paqueteSlug) {
    // Paquete no encontrado: 404, no caer a la pesca por defecto.
    if (!paquete) notFound();
    const empresasDeTraslado = [
      ...new Set(
        paquete.servicios_asociados
          .filter((c) => c.servicio.tipo_servicio === 'transporte')
          .map((c) => c.servicio.empresa_slug),
      ),
    ];
    const catalogos = await Promise.all(
      empresasDeTraslado.map((empresa) => getTraslados(empresa).catch(() => null)),
    );
    const tarifasPorEmpresa: Record<string, TrasladosCatalogo['tarifas']> = {};
    const puntosPorEmpresa: Record<string, TrasladosCatalogo['puntos_encuentro']> = {};
    empresasDeTraslado.forEach((empresa, i) => {
      tarifasPorEmpresa[empresa] = catalogos[i]?.tarifas ?? [];
      puntosPorEmpresa[empresa] = catalogos[i]?.puntos_encuentro ?? [];
    });
    return (
      <PedidoPaquete
        lang={lang}
        dict={dict}
        paquete={paquete}
        sedeSlug={paquete.sede_slug}
        tarifasPorEmpresa={tarifasPorEmpresa}
        puntosPorEmpresa={puntosPorEmpresa}
        minDate={minDate}
      />
    );
  }

  // Resolución de empresa dinámicamente según el ítem seleccionado:
  // - paquete -> paquete.empresa_lider_slug
  // - servicio suelto -> servicio.empresa_slug (query.empresa)
  // - pesca legacy -> NEXT_PUBLIC_EMPRESA_SLUG
  const servicioSlug = typeof query.servicio === 'string' ? query.servicio : undefined;
  const servicioEmpresa = typeof query.empresa === 'string' ? query.empresa : undefined;
  const paqueteEmpresa = typeof query.paquete_empresa === 'string' ? query.paquete_empresa : undefined;
  const defaultEmpresaSlug = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

  const empresaSlug = paquete?.empresa_lider_slug ?? paqueteEmpresa ?? servicioEmpresa ?? defaultEmpresaSlug;

  let servicio: ServicioCatalogo | null = null;
  if (!paqueteSlug) {
    const slug = servicioSlug ?? 'pesca-deportiva';
    servicio = await getServicioDetalle(slug, empresaSlug).catch(() => null);
  }

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
      queryOverride={queryOverride}
      empresaSlug={empresaSlug}
      servicioId={servicio?.slug ?? null}
      servicioNombre={servicio?.nombre ?? null}
      servicio={servicio}
    />
  );
}
