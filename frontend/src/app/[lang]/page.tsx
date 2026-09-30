import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import { alternativasDe } from '@/lib/site';
import { getSedes } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import type { SedeContenido } from '@/content/sedes-tipos';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { HubMapaSedes } from '@/components/hub-mapa-sedes';
import { HubGridSedes } from '@/components/hub-grid-sedes';
import { HubPorQue } from '@/components/hub-por-que';
import { ColaboradoresSection } from '@/components/colaboradores-section';

export async function generateMetadata({ params }: PageProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return { title: { absolute: dict.hub.meta.title }, description: dict.hub.meta.description, alternates: alternativasDe(lang) };
}

export default async function Home({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const sedesApi = await getSedes().catch(() => null);
  const sedes = sedesActivas(SEDES_INDICE, sedesApi).map(s => getSedeContenido(s.slug, lang)).filter((s): s is SedeContenido => !!s);
  return <>
    <SiteHeader lang={lang} nav={dict.nav} variante="hub" />
    <main>
      <section id="hub-mapa-destinos" className="scroll-mt-28 mx-auto max-w-[1440px] px-6 pb-12 pt-[calc(var(--nav-alto)+3rem)] sm:px-8 lg:px-12">
        <div className="mb-8 max-w-3xl">
          <p className="mb-3 text-sm font-semibold text-accent">{dict.hub.nombreAgencia}</p>
          <h1 className="text-5xl leading-[1.05] text-foreground sm:text-6xl">{dict.hub.headline}</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">{dict.hub.mision}</p>
        </div>
        <HubMapaSedes lang={lang} sedes={sedes} copy={dict.hub} />
      </section>
      <section id="sedes" className="scroll-mt-28 mx-auto max-w-[1440px] px-6 py-12 sm:px-8 lg:px-12">
        <h2 className="mb-8 text-4xl sm:text-5xl">{dict.hub.destinationsTitle}</h2>
        <HubGridSedes lang={lang} sedes={sedes} copy={dict.hub} />
      </section>
      <HubPorQue headline={dict.hub.aboutTitle} pilares={dict.hub.pilares} />
      <ColaboradoresSection sedes={sedes} lang={lang} copy={dict.hub} />
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} negocio={null} />
  </>;
}
