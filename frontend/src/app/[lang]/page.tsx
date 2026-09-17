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
import { HubHero } from '@/components/hub-hero';
import { HubMapaSedes } from '@/components/hub-mapa-sedes';
import { HubGridSedes } from '@/components/hub-grid-sedes';
import { HubPorQue } from '@/components/hub-por-que';

const MAPA_ANCHOR_ID = 'hub-mapa-destinos';

export async function generateMetadata({ params }: PageProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};

  const dict = await getDictionary(lang);
  return {
    title: { absolute: dict.hub.meta.title },
    description: dict.hub.meta.description,
    alternates: alternativasDe(lang),
  };
}

export default async function Home({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const sedesApi = await getSedes().then((s) => s, () => null);
  // `sedesActivas` opera solo sobre el indice (client-safe, chico) — para
  // pintar el mapa/grid con foto (`hero.imagen`) hace falta el cuerpo
  // (server-only) de cada sede activa, combinado aqui, server-side.
  const activas = sedesActivas(SEDES_INDICE, sedesApi);
  const sedes = activas
    .map((entrada) => getSedeContenido(entrada.slug, lang))
    .filter((s): s is SedeContenido => s !== undefined);

  return (
    <>
      <SiteHeader lang={lang} nav={dict.nav} variante="hub" />
      <main>
        <HubHero
          nombreAgencia={dict.hub.nombreAgencia}
          mision={dict.hub.mision}
          ctaLabel={dict.hub.ctaElegirDestino}
          mapaAnchorId={MAPA_ANCHOR_ID}
        />

        <section id={MAPA_ANCHOR_ID} className="scroll-mt-24 mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12">
          <HubMapaSedes
            lang={lang}
            sedes={sedes}
            verDestinoLabel={dict.hub.verDestino}
            conLabel={dict.hub.conLabel}
          />
          <div className="mt-12">
            <HubGridSedes
              lang={lang}
              sedes={sedes}
              verDestinoLabel={dict.hub.verDestino}
              conLabel={dict.hub.conLabel}
            />
          </div>
        </section>

        <HubPorQue headline={dict.hub.porQueHeadline} pilares={dict.hub.pilares} />
      </main>
      <SiteFooter
        lang={lang}
        footer={dict.footer}
        nav={dict.nav}
        bookLabel={dict.booking.submit}
        negocio={null}
      />
    </>
  );
}
