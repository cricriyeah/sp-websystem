import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { TextoLegal } from '@/components/texto-legal';
import { LegalBackLink } from '@/components/legal-back-link';
import { alternativasDe } from '@/lib/site';

export async function generateMetadata({
  params,
}: PageProps<'/[lang]/cancelaciones'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};

  const dict = await getDictionary(lang);
  return {
    title: dict.meta.cancelaciones.title,
    description: dict.meta.cancelaciones.description,
    alternates: alternativasDe(lang, '/cancelaciones'),
  };
}

export default async function CancelacionesPage({ params }: PageProps<'/[lang]/cancelaciones'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const { cancelaciones: politica } = dict;

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" />

      {/* SiteHeader es `fixed` y no reserva espacio: sin `--nav-alto` (ver
          globals.css) el contenido arrancaria debajo de la barra. El 3rem es
          la separacion que llevaba de siempre. */}
      <main className="mx-auto max-w-3xl px-pagina pt-[calc(3rem_+_var(--nav-alto))] pb-12">
        <LegalBackLink label={politica.back} fallbackHref={`/${lang}`} />

        <h1 className="mt-8 texto-pagina text-foreground">
          {politica.title}
        </h1>
        <p className="mt-2 texto-cuerpo">{politica.updated}</p>
        <div className="mt-6">
          <TextoLegal texto={politica.intro} />
        </div>

        <div className="mt-14 flex flex-col gap-10">
          {politica.sections.map((section) => (
            <section key={section.title}>
              <h2 className="texto-subtitulo text-foreground">
                {section.title}
              </h2>
              <div className="mt-3">
                <TextoLegal texto={section.body} />
              </div>
            </section>
          ))}
        </div>
      </main>

      <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={null} />
    </div>
  );
}
