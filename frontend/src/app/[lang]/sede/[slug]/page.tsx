import type { Metadata } from 'next';
import { notFound, permanentRedirect } from 'next/navigation';
import Link from 'next/link';
import { getDictionary, hasLocale } from '../../dictionaries';
import { alternativasDe } from '@/lib/site';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getPaquetesSede, getServiciosSede, type Moneda } from '@/lib/api';
import { getMinBookableDate } from '@/lib/dates';
import { hrefDetalleServicio, hrefServicio } from '@/lib/booking-href';
import { hrefSede } from '@/lib/routes';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SedeHero } from '@/components/sede-hero';
import { PaqueteCard } from '@/components/paquete-card';
import { ServiciosSueltosSection } from '@/components/servicios-sueltos-section';
import { AboutSection } from '@/components/about-section';
import { SeasonSection } from '@/components/season-section';
import { GallerySection } from '@/components/gallery-section';
import { ReviewsSection } from '@/components/reviews-section';
import { FaqSection } from '@/components/faq-section';
import { StructuredData } from '@/components/structured-data';
import { StickyBookingBar } from '@/components/sticky-booking-bar';
import { ProveedorReserva } from '@/components/booking-state';
import { ColaboradoresSection } from '@/components/colaboradores-section';
import { SedePendingSection } from '@/components/sede-pending-section';

type Props = { params: Promise<{ lang: string; slug: string }>; searchParams: Promise<{ moneda?: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) return {};
  const contenido = getSedeContenido(slug, lang);
  if (!contenido) return {};
  return { title: { absolute: contenido.metaTitle }, description: contenido.metaDescription, alternates: alternativasDe(lang, `/sede/${slug}`) };
}

export default async function SedePage({ params, searchParams }: Props) {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) notFound();
  if (slug === 'los-cabos') permanentRedirect(hrefSede(lang, 'la-ventana'));
  const contenido = getSedeContenido(slug, lang);
  if (!contenido) notFound();
  const dict = await getDictionary(lang);
  const query = await searchParams;
  const moneda: Moneda = typeof query.moneda === 'string' && query.moneda.toUpperCase() === 'USD' ? 'USD' : 'MXN';
  const [paquetes, servicios] = await Promise.all([getPaquetesSede(slug).catch(() => []), getServiciosSede(slug).catch(() => [])]);
  const minDate = getMinBookableDate();
  const laPaz = slug === 'la-paz';
  const pagina = <>
    <StructuredData lang={lang} slug={slug} negocio={contenido.negocio} description={contenido.metaDescription} faqItems={laPaz ? dict.faq.items : null} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" sedeSlugActual={slug} />
    <main>
      <SedeHero lang={lang} sedeSlug={slug} contenido={{ ...contenido.hero, facts: [] }} destacadas={contenido.destacadas} paquetes={paquetes} servicios={servicios} moneda={moneda} booking={dict.booking} minDate={minDate} verTodoLabel={dict.catalog.verTodo} hrefVerTodo={hrefSede(lang, slug, 'experiencias')} precioDesdeLabel={dict.catalog.fromPrice} />
      <AboutSection about={{ headline: contenido.colaboracion.titulo, body1: contenido.colaboracion.texto1, body2: contenido.colaboracion.texto2, photoHint: contenido.colaboracion.imagenAlt }} imagenSrc={contenido.colaboracion.imagenSrc} imagenAlt={contenido.colaboracion.imagenAlt} />
      <ColaboradoresSection sedes={[contenido]} lang={lang} copy={dict.hub} id="empresas" />
      <section id="experiencias" className="scroll-mt-28 mx-auto max-w-6xl px-6 py-12 sm:px-8 lg:px-12">
        <h2 className="mb-8 text-4xl sm:text-5xl">{dict.catalog.title}</h2>
        {paquetes.length ? <div className="grid items-start gap-8 md:grid-cols-2">{paquetes.map(paquete => <PaqueteCard key={paquete.id} paquete={paquete} lang={lang} dict={dict.catalog} moneda={moneda} />)}</div> : <p className="rounded-2xl bg-surface p-8 text-muted">{dict.catalog.emptyPackages}</p>}
      </section>
      <section id="servicios" className="scroll-mt-28 mx-auto max-w-6xl px-6 py-12 sm:px-8 lg:px-12">
        <ServiciosSueltosSection servicios={servicios} lang={lang} dict={dict.catalog} moneda={moneda} mostrarVacio sedeSlug={slug} />
        {contenido.servicioTransporte && !servicios.some(s => s.tipo_servicio === 'transporte' && s.empresa_slug === contenido.servicioTransporte?.empresaSlug) && <article className="mt-8 rounded-2xl border border-border bg-surface p-6 sm:p-8">
          <h3 className="text-2xl">{dict.traslados.title}</h3>
          <p className="mt-2 max-w-2xl text-sm text-muted">{dict.traslados.subtitle}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={hrefServicio({ slug: 'traslados-la-paz', empresa_slug: contenido.servicioTransporte.empresaSlug, tipo_servicio: 'transporte' }, lang, moneda)} className="rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white">{dict.destination.book}</Link>
            <Link href={hrefDetalleServicio({ slug: 'traslados-la-paz', empresa_slug: contenido.servicioTransporte.empresaSlug }, lang, moneda, slug)} className="rounded-full border border-border px-5 py-3 text-sm font-semibold hover:border-accent">{dict.destination.learnMore}</Link>
          </div>
        </article>}
      </section>
      {laPaz ? <SeasonSection season={{ ...dict.season, headline: dict.destination.seasonsTitle }} /> : <SedePendingSection id="temporadas" title={dict.destination.seasonsTitle} body={dict.destination.pendingBody} />}
      {laPaz ? <GallerySection gallery={dict.gallery} /> : <SedePendingSection id="galeria" title={dict.destination.galleryTitle} body={dict.destination.pendingBody} />}
      {laPaz ? <ReviewsSection nav={dict.nav} reviews={dict.reviews} /> : <SedePendingSection id="resenas" title={dict.destination.reviewsTitle} body={dict.destination.pendingBody} />}
      {laPaz ? <FaqSection faq={dict.faq} /> : <SedePendingSection id="preguntas" title={dict.destination.faqTitle} body={dict.destination.pendingBody} />}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} negocio={contenido.negocio} sedeSlug={slug} />
    {laPaz && <StickyBookingBar lang={lang} booking={dict.booking} minDate={minDate} />}
  </>;
  return laPaz ? <ProveedorReserva>{pagina}</ProveedorReserva> : pagina;
}
