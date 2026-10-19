import type { Metadata } from 'next';
import { Fragment, type ReactNode } from 'react';
import { notFound, permanentRedirect } from 'next/navigation';
import { getDictionary, hasLocale } from '../../dictionaries';
import { alternativasDe } from '@/lib/site';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getEmpresa } from '@/content/empresas';
import { getPaquetesSede, getServiciosSede, type Moneda } from '@/lib/api';
import { hrefSede } from '@/lib/routes';
import { ANCLA_DE, enlacesDeSede, fondosDeSecciones, seccionesDeSede, type SeccionId } from '@/lib/secciones-sede';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SedeHero } from '@/components/sede-hero';
import { BandaColaboracion } from '@/components/banda-colaboracion';
import { QuePuedesReservar } from '@/components/que-puedes-reservar';
import { SeasonSection } from '@/components/season-section';
import { GallerySection } from '@/components/gallery-section';
import { FaqSection } from '@/components/faq-section';
import { StructuredData } from '@/components/structured-data';
import type { Fondo } from '@/components/ui/section-shell';

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
  const query = await searchParams;
  const moneda: Moneda = typeof query.moneda === 'string' && query.moneda.toUpperCase() === 'USD' ? 'USD' : 'MXN';
  const [dict, paquetes, servicios] = await Promise.all([getDictionary(lang), getPaquetesSede(slug).catch(() => null), getServiciosSede(slug).catch(() => null)]);
  const protagonista = getEmpresa(contenido.empresaProtagonistaSlug);
  const marcaSede = protagonista ? { nombre: protagonista.nombre, logo: protagonista.logo } : undefined;
  const empresas = [protagonista, ...contenido.otrasEmpresas.map(getEmpresa)].filter((e) => e !== undefined);
  const { galeria, temporadas, faq } = contenido;

  // Cada sección que sabe pintarse; «Reserva con tranquilidad» (9.2) y las opiniones (9.5)
  // aún no tienen componente, así que no entran al cálculo de fondos ni al menú.
  type Banda = { fondo: Fondo; borde: boolean };
  const pintar: Partial<Record<SeccionId, (banda: Banda) => ReactNode>> = {
    hero: () => <>
      <SedeHero lang={lang} sedeSlug={slug} contenido={{ ...contenido.hero, facts: [] }} destacadas={contenido.destacadas} paquetes={paquetes ?? []} servicios={servicios ?? []} moneda={moneda} booking={dict.booking} verTodoLabel={dict.catalog.verTodo} hrefVerTodo={hrefSede(lang, slug, ANCLA_DE.reservar)} precioDesdeLabel={dict.catalog.fromPrice} />
      {marcaSede && <BandaColaboracion empresa={marcaSede} frase={dict.sedeContenido.colaboracion} />}
    </>,
    reservar: (banda) => <QuePuedesReservar lang={lang} moneda={moneda} sede={{ slug, nombre: contenido.nombre }} servicios={servicios} paquetes={paquetes} estado={secciones.find((x) => x.id === 'reservar')?.estado ?? 'normal'} destacadas={contenido.destacadas} textos={dict.sedeContenido.queReservar} {...banda} />,
    ...(galeria && { galeria: (banda: Banda) => <GallerySection id={ANCLA_DE.galeria} titulo={dict.sedeContenido.galeria} fotos={galeria} {...banda} /> }),
    ...(temporadas && { temporadas: (banda: Banda) => <SeasonSection id={ANCLA_DE.temporadas} titulo={dict.destination.seasonsTitle} temporadas={temporadas} {...banda} /> }),
    ...(faq && { preguntas: (banda: Banda) => <FaqSection id={ANCLA_DE.preguntas} titulo={dict.sedeContenido.faq} preguntas={faq} {...banda} /> }),
  };
  const secciones = seccionesDeSede({
    servicios,
    paquetes,
    resenas: empresas.flatMap((e) => e.resenas),
    fotos: galeria ?? [],
    faq: faq ?? [],
    temporadas: temporadas?.filas,
  });
  const ids = secciones.map((s) => s.id).filter((id) => pintar[id]);
  const fondos = fondosDeSecciones(ids);
  const anclas = enlacesDeSede(ids).map(({ ancla, claveNav }) => ({ ancla, etiqueta: dict.nav[claveNav] }));

  return <>
    <StructuredData lang={lang} slug={slug} negocio={contenido.negocio} description={contenido.metaDescription} faqItems={faq ?? null} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" sedeSlugActual={slug} marcaSede={marcaSede} anclas={anclas} />
    <main>
      {ids.map((id) => <Fragment key={id}>{pintar[id]?.(fondos[id] ?? { fondo: 'arena', borde: true })}</Fragment>)}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} negocio={contenido.negocio} sedeSlug={slug} anclas={anclas} />
  </>;
}
