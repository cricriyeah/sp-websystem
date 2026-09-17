// frontend/src/app/[lang]/sede/[slug]/page.tsx
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ArrowRight, Car } from '@phosphor-icons/react/ssr';
import Link from 'next/link';
import { getDictionary, hasLocale } from '../../dictionaries';
import { alternativasDe } from '@/lib/site';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getPaquetesSede, getServiciosSede, type Moneda } from '@/lib/api';
import { getMinBookableDate } from '@/lib/dates';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SedeHero } from '@/components/sede-hero';
import { PaqueteCard } from '@/components/paquete-card';
import { ServiciosSueltosSection } from '@/components/servicios-sueltos-section';
import { AboutSection } from '@/components/about-section';
import { SeasonSection } from '@/components/season-section';
import { IncludedSection } from '@/components/included-section';
import { LicenseSection } from '@/components/license-section';
import { GallerySection } from '@/components/gallery-section';
import { ReviewsSection } from '@/components/reviews-section';
import { FaqSection } from '@/components/faq-section';
import { StructuredData } from '@/components/structured-data';
import { StickyBookingBar } from '@/components/sticky-booking-bar';
import { ProveedorReserva } from '@/components/booking-state';

type PageProps = {
  params: Promise<{ lang: string; slug: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) return {};
  const contenido = getSedeContenido(slug, lang);
  if (!contenido) return {};
  return {
    title: { absolute: contenido.metaTitle },
    description: contenido.metaDescription,
    alternates: alternativasDe(lang, `/sede/${slug}`),
  };
}

export default async function SedePage({ params, searchParams }: PageProps) {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) notFound();

  const contenido = getSedeContenido(slug, lang);
  if (!contenido) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;
  const moneda: Moneda =
    typeof query.moneda === 'string' && query.moneda.toUpperCase() === 'USD' ? 'USD' : 'MXN';
  const minDate = getMinBookableDate();

  const [paquetes, servicios] = await Promise.all([
    getPaquetesSede(slug).catch(() => []),
    getServiciosSede(slug).catch(() => []),
  ]);

  // El contenido largo (temporada/incluye/licencia/galeria/resenas/faq) sigue
  // viviendo en el diccionario global — hoy es identico a lo que ya es
  // correcto para la-paz; cualquier otra sede lo recibe en null (spec §4,
  // §6.6-6.8) hasta que tenga su propio contenido real.
  const contenidoLargo =
    slug === 'la-paz'
      ? {
          temporada: dict.season,
          incluye: dict.included,
          licencia: dict.license,
          galeria: dict.gallery,
          resenas: dict.reviews,
          faq: dict.faq,
        }
      : { temporada: null, incluye: null, licencia: null, galeria: null, resenas: null, faq: null };

  const pagina = (
    <>
      <StructuredData
        lang={lang}
        slug={slug}
        negocio={contenido.negocio}
        description={contenido.metaDescription}
        faqItems={contenidoLargo.faq?.items ?? null}
      />
      <SiteHeader lang={lang} nav={dict.nav} variante="sede" sedeSlugActual={slug} />

        <main>
          <SedeHero
            lang={lang}
            sedeSlug={slug}
            contenido={contenido.hero}
            destacadas={contenido.destacadas}
            paquetes={paquetes}
            servicios={servicios}
            moneda={moneda}
            booking={dict.booking}
            minDate={minDate}
            verTodoLabel={dict.catalog.verTodo}
            hrefVerTodo={`/${lang}/sede/${slug}#experiencias`}
          />

          <section id="experiencias" className="scroll-mt-24 mx-auto max-w-6xl px-6 pt-12 sm:px-8 lg:px-12">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-bold tracking-tight text-foreground sm:text-xl">
                {dict.catalog.title}
              </h2>
              <span className="text-xs text-muted">
                {paquetes.length} {paquetes.length === 1 ? 'paquete' : 'paquetes'}
              </span>
            </div>

            {paquetes.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border bg-card/60 p-12 text-center">
                <p className="text-muted">{dict.catalog.emptyPackages}</p>
              </div>
            ) : (
              <div className="grid gap-8 md:grid-cols-2 items-start">
                {paquetes.map((paquete) => (
                  <PaqueteCard key={paquete.id} paquete={paquete} lang={lang} dict={dict.catalog} moneda={moneda} />
                ))}
              </div>
            )}

            <ServiciosSueltosSection servicios={servicios} lang={lang} dict={dict.catalog} moneda={moneda} />

            {contenido.servicioTransporte && (
              <section className="mt-12 rounded-2xl border border-border bg-card/60 p-6 sm:p-8">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                      <Car size={24} weight="duotone" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-foreground sm:text-lg">{dict.traslados.title}</h3>
                      <p className="mt-1 text-xs text-muted leading-relaxed sm:text-sm">{dict.traslados.subtitle}</p>
                    </div>
                  </div>
                  <Link
                    href={`/${lang}${contenido.servicioTransporte.hrefTraslados}`}
                    className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-5 py-2.5 text-xs font-semibold text-foreground transition-colors hover:border-accent hover:text-accent sm:self-auto"
                  >
                    <span>{dict.traslados.cta}</span>
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </section>
            )}
          </section>

          <AboutSection
            about={{
              headline: contenido.colaboracion.titulo,
              body1: contenido.colaboracion.texto1,
              body2: contenido.colaboracion.texto2,
              photoHint: contenido.colaboracion.imagenAlt,
            }}
            imagenSrc={contenido.colaboracion.imagenSrc}
            imagenAlt={contenido.colaboracion.imagenAlt}
          />

          {contenidoLargo.temporada && <SeasonSection season={contenidoLargo.temporada} />}
          {contenidoLargo.incluye && <IncludedSection included={contenidoLargo.incluye} />}
          {contenidoLargo.licencia && <LicenseSection nav={dict.nav} license={contenidoLargo.licencia} />}

          {contenido.otrasEmpresas.length > 0 && (
            <section className="mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12">
              <h2 className="text-xl font-bold text-foreground">{dict.hub.conLabel} más en {contenido.negocio?.ciudad ?? contenido.empresaFundadoraNombre}</h2>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {contenido.otrasEmpresas.map((empresa) => (
                  <a
                    key={empresa.slug}
                    href={empresa.enlaceExterno}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4 transition-colors hover:border-accent"
                  >
                    <span className="text-sm font-semibold text-foreground">{empresa.nombre}</span>
                    <span className="text-xs text-muted">{empresa.descripcion}</span>
                  </a>
                ))}
              </div>
            </section>
          )}

          {contenidoLargo.galeria && <GallerySection gallery={contenidoLargo.galeria} />}
          {contenidoLargo.resenas && <ReviewsSection nav={dict.nav} reviews={contenidoLargo.resenas} />}
          {contenidoLargo.faq && <FaqSection faq={contenidoLargo.faq} />}
        </main>

        <SiteFooter
          lang={lang}
          footer={dict.footer}
          nav={dict.nav}
          bookLabel={dict.booking.submit}
          negocio={contenido.negocio}
          sedeSlug={slug}
        />

        {slug === 'la-paz' && <StickyBookingBar lang={lang} booking={dict.booking} minDate={minDate} />}
    </>
  );
  return slug === 'la-paz' ? <ProveedorReserva>{pagina}</ProveedorReserva> : pagina;
}
