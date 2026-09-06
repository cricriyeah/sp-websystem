import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SedeSelector } from '@/components/sede-selector';
import { PaqueteCard } from '@/components/paquete-card';
import { ServiciosSueltosSection } from '@/components/servicios-sueltos-section';
import { getPaquetesSede, getSedes, getServiciosSede, type Moneda } from '@/lib/api';
import { alternativasDe } from '@/lib/site';

type PageProps = {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return {
    title: dict.meta.catalogo?.title ?? 'Experiencias y Paquetes | Sal y Sol',
    description: dict.meta.catalogo?.description ?? '',
    alternates: alternativasDe(lang, '/catalogo'),
  };
}

export default async function CatalogoPage({ params, searchParams }: PageProps) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;

  const sedeQuery = typeof query.sede === 'string' ? query.sede : undefined;
  const monedaQuery: Moneda =
    typeof query.moneda === 'string' && query.moneda.toUpperCase() === 'USD'
      ? 'USD'
      : 'MXN';

  // Obtener sedes disponibles
  const sedes = await getSedes().catch(() => []);

  // Resolver la sede seleccionada (default: coincidencia con query o primera sede o 'la-paz')
  const sedeActual =
    (sedeQuery ? sedes.find((s) => s.slug === sedeQuery) : null) ??
    sedes[0] ?? {
      id: 1,
      nombre: 'La Paz',
      slug: 'la-paz',
      zona_horaria: 'America/Mazatlan',
    };

  // Cargar paquetes y servicios de la localidad seleccionada en paralelo
  const [paquetes, servicios] = await Promise.all([
    getPaquetesSede(sedeActual.slug).catch(() => []),
    getServiciosSede(sedeActual.slug).catch(() => []),
  ]);

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={dict.nav} />

      <main className="mx-auto max-w-6xl px-6 pt-[calc(3rem_+_var(--nav-alto))] pb-20 sm:px-8 lg:px-12">
        {/* Cabecera del Catálogo y Selector de Destino */}
        <div className="flex flex-col gap-6 border-b border-border/70 pb-8 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-2xl">
            <span className="text-xs font-semibold uppercase tracking-widest text-accent">
              Baja California Sur
            </span>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl lg:text-5xl">
              {dict.catalog.title}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-muted sm:text-base">
              {dict.catalog.subtitle}
            </p>
          </div>

          <div className="flex flex-col items-start sm:items-end">
            <span className="mb-2 text-xs font-medium text-muted">
              {dict.catalog.selectDestination}:
            </span>
            <SedeSelector
              lang={lang}
              sedes={sedes}
              sedeSeleccionadaSlug={sedeActual.slug}
              label={dict.catalog.selectDestination}
              variant="catalog"
            />
          </div>
        </div>

        {/* Sección Dominante: Paquetes de Experiencias (Perception-First Design) */}
        <section className="mt-10">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-lg font-bold tracking-tight text-foreground sm:text-xl">
              Experiencias recomendadas en {sedeActual.nombre}
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
                <PaqueteCard
                  key={paquete.id}
                  paquete={paquete}
                  lang={lang}
                  dict={dict.catalog}
                  moneda={monedaQuery}
                />
              ))}
            </div>
          )}
        </section>

        {/* Camino Secundario: Servicios Sueltos */}
        <ServiciosSueltosSection
          servicios={servicios}
          lang={lang}
          dict={dict.catalog}
          moneda={monedaQuery}
        />
      </main>

      <SiteFooter
        lang={lang}
        footer={dict.footer}
        nav={dict.nav}
        bookLabel={dict.booking.submit}
      />
    </div>
  );
}
