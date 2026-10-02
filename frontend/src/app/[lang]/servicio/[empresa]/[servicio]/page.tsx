import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { cache } from 'react';
import { getDictionary, hasLocale } from '../../../dictionaries';
import { ApiError, getServicioDetalle } from '@/lib/api';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { alternativasDe } from '@/lib/site';
import { hrefServicio } from '@/lib/booking-href';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { IncludedSection } from '@/components/included-section';

type Props = {
  params: Promise<{ lang: string; empresa: string; servicio: string }>;
  searchParams: Promise<{ sede?: string; moneda?: string }>;
};
const cargar = cache(async (slug: string, empresa: string) => {
  try { return { data: await getServicioDetalle(slug, empresa), missing: false }; }
  catch (error) { return { data: null, missing: error instanceof ApiError && error.status === 404 }; }
});
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, empresa, servicio } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  const result = await cargar(servicio, empresa);
  const title = result.data?.nombre ?? (servicio === 'pesca-deportiva' ? dict.serviceDetail.fishingTitle : dict.serviceDetail.metaFallback);
  return { title, alternates: alternativasDe(lang, `/servicio/${empresa}/${servicio}`) };
}
export default async function ServicioPage({ params, searchParams }: Props) {
  const { lang, empresa, servicio: slug } = await params;
  if (!hasLocale(lang)) notFound();
  const pesca = empresa === 'sal-y-sol' && slug === 'pesca-deportiva';
  const { data: servicio, missing } = await cargar(slug, empresa);
  const traslado = servicio?.tipo_servicio === 'transporte' || (empresa === 'transporte-la-paz' && slug === 'traslados-la-paz');
  if (missing && !pesca && !traslado) notFound();
  const query = await searchParams;
  const sede = getSedeContenido(typeof query.sede === 'string' ? query.sede : 'la-paz', lang);
  const dict = await getDictionary(lang);
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  const titulo = servicio?.nombre ?? (pesca ? dict.serviceDetail.fishingTitle : traslado ? dict.traslados.title : dict.serviceDetail.metaFallback);
  const hrefReserva = servicio
    ? hrefServicio(servicio, lang, moneda)
    : pesca || traslado
      ? hrefServicio({ slug, empresa_slug: empresa, tipo_servicio: traslado ? 'transporte' : 'pesca' }, lang, moneda)
      : null;
  return <>
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede?.slug} />
    <main>
      <section className="mx-auto max-w-6xl px-6 pb-16 pt-[calc(var(--nav-alto)+3rem)] sm:px-8 lg:px-12">
        <Link href={sede ? hrefSede(lang, sede.slug, 'servicios') : hrefInicio(lang, 'sedes')} className="text-sm text-accent underline underline-offset-4">{dict.serviceDetail.backToServices}</Link>
        <h1 className="mt-8 max-w-3xl text-5xl leading-tight sm:text-6xl">{titulo}</h1>
        <p className="mt-5 max-w-3xl whitespace-pre-line text-lg leading-relaxed text-muted">{servicio?.descripcion || (pesca ? dict.serviceDetail.fishingDescription : traslado ? dict.traslados.subtitle : dict.serviceDetail.unavailableDescription)}</p>
        {servicio && !traslado && <p className="mt-6 text-xl font-semibold">{dict.catalog.fromPrice} {formatearPrecio(aMoneda(servicio.precio_base, moneda, servicio.tipo_cambio_usd), moneda)} {moneda}</p>}
        {hrefReserva && <Link href={hrefReserva} className="mt-8 inline-flex rounded-full bg-accent px-7 py-3.5 text-sm font-semibold text-white">{dict.serviceDetail.book}</Link>}
        {pesca && <dl className="mt-12 grid gap-6 border-t border-border pt-8 sm:grid-cols-2 lg:grid-cols-4">{getSedeContenido('la-paz', lang)?.hero.facts.map(fact => <div key={fact.label}><dt className="text-sm text-muted">{fact.label}</dt><dd className="mt-2 text-xl font-semibold text-accent">{fact.value}</dd></div>)}</dl>}
      </section>
      {pesca && <IncludedSection included={dict.included} />}
      {servicio && !pesca && !traslado && <section className="bg-surface py-16"><div className="mx-auto grid max-w-6xl gap-8 px-6 sm:grid-cols-2 sm:px-8 lg:px-12"><div><h2 className="text-3xl">{dict.serviceDetail.detailsTitle}</h2><p className="mt-4 text-muted">{dict.serviceDetail.includedGuests} {servicio.personas_incluidas}</p></div><div><h3 className="text-2xl">{dict.serviceDetail.beforeBookingTitle}</h3><p className="mt-4 text-muted">{dict.serviceDetail.beforeBookingBody}</p></div></div></section>}
      {traslado && <section className="bg-surface py-16"><div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12"><h2 className="text-4xl">{dict.serviceDetail.transferIncludedTitle}</h2><p className="mt-5 max-w-2xl text-muted">{dict.traslados.summary.included}</p><p className="mt-4 max-w-2xl text-muted">{dict.serviceDetail.transferInstructions}</p></div></section>}
      {!!servicio?.personalizaciones.length && <section className="mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12"><h2 className="text-4xl">{dict.serviceDetail.customizeTitle}</h2><div className="mt-8 grid gap-4 sm:grid-cols-2">{servicio.personalizaciones.map(extra => <article key={extra.id} className="rounded-xl border border-border p-6"><h3 className="text-xl">{extra.nombre}</h3><p className="mt-2 text-sm text-muted">{dict.serviceDetail.optionalPrice}</p></article>)}</div></section>}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} />
  </>;
}
