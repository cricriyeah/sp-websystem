import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { PaqueteCheckout } from '@/components/paquete-checkout';
import { getPaqueteDetalle, getSedes, getTraslados, type PaqueteCatalogo, type TrasladosCatalogo } from '@/lib/api';
import { esPaqueteCruzaEmpresa } from '@/lib/pricing-paquete';
import { alternativasDe } from '@/lib/site';

export async function generateMetadata({
  params,
}: PageProps<'/[lang]/reservar-paquete'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return {
    title: dict.meta.reservarPaquete.title,
    description: dict.meta.reservarPaquete.description,
    alternates: alternativasDe(lang, '/reservar-paquete'),
    // Fuera del indice, mismo criterio que /reservar: es un paso del embudo.
    robots: { index: false, follow: true },
  };
}

export default async function ReservarPaquetePage({
  params,
  searchParams,
}: PageProps<'/[lang]/reservar-paquete'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;

  const paqueteSlug = typeof query.paquete === 'string' ? query.paquete : undefined;
  const sedeSlugParam = typeof query.sede === 'string' ? query.sede : undefined;
  if (!paqueteSlug) notFound();

  let paquete: PaqueteCatalogo | null = null;
  let sedeSlug = sedeSlugParam;

  if (sedeSlug) {
    paquete = await getPaqueteDetalle(sedeSlug, paqueteSlug).catch(() => null);
  } else {
    const sedes = await getSedes().catch(() => []);
    for (const s of sedes) {
      const p = await getPaqueteDetalle(s.slug, paqueteSlug).catch(() => null);
      if (p) {
        paquete = p;
        sedeSlug = s.slug;
        break;
      }
    }
  }

  if (!paquete || !sedeSlug) notFound();
  // Este checkout es solo para paquetes cruza-empresa; uno de una sola
  // empresa debe ir por el checkout de reserva sencilla (/reservar).
  if (!esPaqueteCruzaEmpresa(paquete)) notFound();

  const componenteTransporte = paquete.servicios_asociados.find(
    (item) => item.servicio.tipo_servicio === 'transporte',
  );
  const trasladoCatalogo: TrasladosCatalogo | null = componenteTransporte
    ? await getTraslados(componenteTransporte.servicio.empresa_slug).catch(() => null)
    : null;

  return (
    <PaqueteCheckout
      lang={lang}
      dict={dict}
      paquete={paquete}
      sedeSlug={sedeSlug}
      trasladoCatalogo={trasladoCatalogo}
    />
  );
}
