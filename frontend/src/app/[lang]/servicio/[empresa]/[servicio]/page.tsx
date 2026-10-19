import type { Metadata } from 'next';
import { botonClases } from '@/components/ui/variantes';
import Image from 'next/image';
import Link from 'next/link';
import { Check } from '@phosphor-icons/react/ssr';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { cache } from 'react';
import { getDictionary, hasLocale } from '../../../dictionaries';
import { API_URL, ApiError, getServicioDetalle } from '@/lib/api';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { alternativasDe } from '@/lib/site';
import { hrefServicio } from '@/lib/booking-href';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { IncludedSection } from '@/components/included-section';
import { ANCLA_DE, ANCLA_HUB } from '@/lib/secciones-sede';
import { claveDeServicio, imagenDeCatalogo } from '@/content/imagenes-catalogo';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

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
  // La conexion es de fetch CORS: sin crossOrigin el navegador abriria otra.
  preconnect(API_URL, { crossOrigin: 'anonymous' });
  const { lang, empresa, servicio: slug } = await params;
  if (!hasLocale(lang)) notFound();
  const pesca = empresa === 'sal-y-sol' && slug === 'pesca-deportiva';
  // Catalogo, query y diccionario no dependen entre si: se piden a la vez.
  const [{ data: servicio, missing }, query, dict] = await Promise.all([cargar(slug, empresa), searchParams, getDictionary(lang)]);
  const traslado = servicio?.tipo_servicio === 'transporte' || (empresa === 'transporte-la-paz' && slug === 'traslados-la-paz');
  if (missing && !pesca && !traslado) notFound();
  const sede = getSedeContenido(typeof query.sede === 'string' ? query.sede : 'la-paz', lang);
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  const titulo = servicio?.nombre ?? (pesca ? dict.serviceDetail.fishingTitle : traslado ? dict.traslados.title : dict.serviceDetail.metaFallback);
  const hrefReserva = servicio
    ? hrefServicio(servicio, lang, moneda, { origen: 'servicio', sede: sede?.slug })
    : pesca || traslado
      ? hrefServicio({ slug, empresa_slug: empresa, tipo_servicio: traslado ? 'transporte' : 'pesca' }, lang, moneda, { origen: 'servicio', sede: sede?.slug })
      : null;
  const foto = imagenDeCatalogo(claveDeServicio(empresa, slug), lang);
  const incluye = servicio?.incluye?.[lang] ?? [];
  const textos = dict.sedeContenido.queReservar;
  // La misma lista que la tarjeta de la sede; sin ella, la pesca de Sal y Sol conserva su sección.
  const bloqueIncluye = servicio && !traslado && (incluye.length > 0 || !pesca) && <div className="mt-10 max-w-3xl">
    <h2 className="texto-subtitulo text-foreground">{textos.incluye}</h2>
    {incluye.length > 0
      ? <ul className="mt-4 flex flex-col gap-2">{incluye.map(renglon => <li key={renglon} className="flex items-start gap-2 texto-cuerpo text-foreground"><Check size={18} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0 text-cafe" /><span>{renglon}</span></li>)}</ul>
      : tieneWhatsapp
        ? <a href={whatsappHref(textos.whatsappMensaje.replace('{sede}', sede?.nombre ?? ''))} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex min-h-11 items-center texto-cuerpo text-cafe">{textos.preguntaIncluye}</a>
        : <p className="mt-3 texto-cuerpo text-muted">{textos.preguntaIncluye}</p>}
  </div>;
  return <>
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede?.slug} />
    <main>
      <section className="mx-auto max-w-6xl px-6 pb-16 pt-[calc(var(--nav-alto)+3rem)] sm:px-8 lg:px-12">
        <Link href={sede ? hrefSede(lang, sede.slug, ANCLA_DE.reservar) : hrefInicio(lang, ANCLA_HUB.sedes)} className="text-sm text-accent underline underline-offset-4">{dict.serviceDetail.backToServices}</Link>
        <h1 className="mt-8 max-w-3xl texto-pagina">{titulo}</h1>
        <p className="mt-5 max-w-3xl whitespace-pre-line text-lg leading-relaxed text-muted">{servicio?.descripcion || (pesca ? dict.serviceDetail.fishingDescription : traslado ? dict.traslados.subtitle : dict.serviceDetail.unavailableDescription)}</p>
        {servicio && !traslado && <p className="mt-6 text-xl font-semibold">{dict.catalog.fromPrice} {formatearPrecio(aMoneda(servicio.precio_base, moneda, servicio.tipo_cambio_usd), moneda)} {moneda}</p>}
        {hrefReserva && <Link href={hrefReserva} className={`mt-8 ${botonClases({ variante: 'principal' })}`}>{dict.serviceDetail.book}</Link>}
        {foto && <div className="relative mt-10 aspect-[16/10] max-w-3xl overflow-hidden rounded-card"><Image src={foto.src} alt={foto.alt} fill priority sizes="(min-width: 768px) 768px, 100vw" className="object-cover" /></div>}
        {bloqueIncluye}
        {pesca && <dl className="mt-12 grid gap-6 border-t border-border pt-8 sm:grid-cols-2 lg:grid-cols-4">{getSedeContenido('la-paz', lang)?.hero.facts.map(fact => <div key={fact.label}><dt className="text-sm text-muted">{fact.label}</dt><dd className="mt-2 text-xl font-semibold text-accent">{fact.value}</dd></div>)}</dl>}
      </section>
      {pesca && incluye.length === 0 && <IncludedSection included={dict.included} />}
      {servicio && !pesca && !traslado && <section className="bg-surface py-16"><div className="mx-auto grid max-w-6xl gap-8 px-6 sm:grid-cols-2 sm:px-8 lg:px-12"><div><h2 className="texto-seccion">{dict.serviceDetail.detailsTitle}</h2><p className="mt-4 text-muted">{dict.serviceDetail.includedGuests} {servicio.personas_incluidas}</p></div><div><h3 className="text-2xl">{dict.serviceDetail.beforeBookingTitle}</h3><p className="mt-4 text-muted">{dict.serviceDetail.beforeBookingBody}</p></div></div></section>}
      {traslado && <section className="bg-surface py-16"><div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12"><h2 className="texto-seccion">{dict.serviceDetail.transferIncludedTitle}</h2><p className="mt-5 max-w-2xl text-muted">{dict.traslados.summary.included}</p><p className="mt-4 max-w-2xl text-muted">{dict.serviceDetail.transferInstructions}</p></div></section>}
      {!!servicio?.personalizaciones.length && <section className="mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12"><h2 className="texto-seccion">{dict.serviceDetail.customizeTitle}</h2><div className="mt-8 grid gap-4 sm:grid-cols-2">{servicio.personalizaciones.map(extra => <article key={extra.id} className="rounded-card border border-border p-6"><h3 className="text-xl">{extra.nombre}</h3><p className="mt-2 text-sm text-muted">{dict.serviceDetail.optionalPrice}</p></article>)}</div></section>}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} />
  </>;
}
