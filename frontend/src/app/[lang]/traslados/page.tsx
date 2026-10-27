import { EMPRESAS } from '@/content/empresas';
import { hrefDeOrigen } from '@/lib/origen';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { Warning, WhatsappLogo } from '@phosphor-icons/react/ssr';
import { getDictionary, hasLocale } from '../dictionaries';
import { API_URL, getTraslados, getSedes } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { alternativasDe } from '@/lib/site';
import { whatsappHref, tieneWhatsapp } from '@/lib/contacto';
import { CabeceraMinima } from '@/components/reserva/cabecera-minima';
import { SiteFooter } from '@/components/site-footer';

import { TrasladoView } from '@/components/traslado-view';

type PageProps = {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return {
    title: dict.meta.traslados.title,
    description: dict.meta.traslados.description,
    alternates: alternativasDe(lang, '/traslados'),
    robots: { index: false, follow: true },
  };
}

export default async function TrasladosPage({ params, searchParams }: PageProps) {
  // La conexion es de fetch CORS: sin crossOrigin el navegador abriria otra.
  preconnect(API_URL, { crossOrigin: 'anonymous' });
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;

  const empresaSlug =
    typeof query.empresa === 'string' && query.empresa
      ? query.empresa
      : (process.env.NEXT_PUBLIC_TRANSPORTE_EMPRESA_SLUG ?? 'transporte-la-paz');

  const sedeDeTransporte = Object.keys(SEDES_INDICE)
    .map((slug) => getSedeContenido(slug, lang))
    .find((contenido) => contenido?.servicioTransporte?.empresaSlug === empresaSlug);
  let sedeSlugActual = sedeDeTransporte?.slug;
  if (!sedeSlugActual) {
    const sedesApi = await getSedes().catch(() => null);
    sedeSlugActual = sedesActivas(SEDES_INDICE, sedesApi)[0]?.slug;
  }
  const catalogo = await getTraslados(empresaSlug, lang).catch(() => null);
  const hrefVolver = hrefDeOrigen({
    lang,
    origen: typeof query.origen === 'string' ? query.origen : undefined,
    sedeSlug: (typeof query.sede === 'string' ? query.sede : undefined) ?? sedeSlugActual,
    rutaServicio: catalogo?.servicio ? `servicio/${empresaSlug}/${catalogo.servicio.slug}` : undefined,
  });

  const empresaEnContenido = EMPRESAS.find((e) => e.slug === empresaSlug);
  const empresaSello = empresaEnContenido ? { nombre: empresaEnContenido.nombre, logo: empresaEnContenido.logo, simbolo: empresaEnContenido.simbolo, simboloBarra: empresaEnContenido.simboloBarra } : undefined;

  if (!catalogo || !catalogo.servicio) {
    return (
      <div className="min-h-dvh bg-background">
        <CabeceraMinima lang={lang} nav={dict.nav} volverHref={hrefVolver} volverLabel={dict.traslados.back} empresa={empresaSello} />
        <div aria-hidden className="h-[calc(1.5rem_+_var(--nav-alto))]" />

        <main className="mx-auto max-w-2xl px-6 py-16 text-center sm:px-8">
          <div className="rounded-card border border-border bg-superficie p-8 sm:p-12">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-accent/10 text-accent">
              <Warning size={32} />
            </div>
            <h1 className="mt-6 texto-seccion text-foreground">
              {dict.traslados.unavailableTitle}
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              {dict.traslados.unavailableMessage}
            </p>
            {tieneWhatsapp && (
              <div className="mt-8">
                <a
                  href={whatsappHref(dict.traslados.unavailableMessage)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-control bg-action px-6 py-3 text-sm font-semibold text-action-foreground transition-transform active:scale-[0.98]"
                >
                  <WhatsappLogo size={20} weight="fill" />
                  {dict.traslados.unavailableCta}
                </a>
              </div>
            )}
          </div>
        </main>

        <SiteFooter
          lang={lang}
          footer={dict.footer}
          nav={dict.nav}
          bookLabel={dict.booking.verQueReservar}
          sedeSlug={sedeSlugActual}
          negocio={sedeDeTransporte?.negocio ?? null}
        />
      </div>
    );
  }

  return (
    <TrasladoView
      lang={lang}
      dict={dict}
      catalogo={catalogo}
      empresaSlug={empresaSlug}
      volverHref={hrefVolver}
      empresa={empresaSello}
    />
  );
}
