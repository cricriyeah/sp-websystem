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
}: PageProps<'/[lang]/privacidad'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};

  const dict = await getDictionary(lang);
  return {
    title: dict.meta.privacidad.title,
    description: dict.meta.privacidad.description,
    alternates: alternativasDe(lang, '/privacidad'),
  };
}

export default async function PrivacidadPage({ params }: PageProps<'/[lang]/privacidad'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const { privacy } = dict;

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={dict.nav} tone="plain" />

      <main className="mx-auto max-w-3xl px-6 py-12 sm:px-8 lg:px-12">
        <LegalBackLink label={privacy.back} fallbackHref={`/${lang}`} />

        <h1 className="mt-8 text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
          {privacy.title}
        </h1>
        <p className="mt-2 text-sm text-muted">{privacy.updated}</p>
        <div className="mt-6">
          <TextoLegal texto={privacy.intro} />
        </div>

        <div className="mt-12 flex flex-col gap-10 border-t border-border pt-10">
          {privacy.sections.map((section) => (
            <section key={section.title}>
              <h2 className="text-base font-medium tracking-tight text-foreground">
                {section.title}
              </h2>
              <div className="mt-3">
                <TextoLegal texto={section.body} />
              </div>
            </section>
          ))}
        </div>
      </main>

      <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} />
    </div>
  );
}
