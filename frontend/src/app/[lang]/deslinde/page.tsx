import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowLeft } from '@phosphor-icons/react/ssr';
import { getDictionary, hasLocale } from '../dictionaries';
import { SiteHeader } from '@/components/site-header';
import { TextoLegal } from '@/components/texto-legal';
import { alternativasDe } from '@/lib/site';

export async function generateMetadata({ params }: PageProps<'/[lang]/deslinde'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return {
    title: dict.meta.deslinde.title,
    description: dict.meta.deslinde.description,
    alternates: alternativasDe(lang, '/deslinde'),
  };
}

export default async function DeslindePage({ params }: PageProps<'/[lang]/deslinde'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const { page } = dict.checkout.waiver;

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={dict.nav} tone="plain" />

      <main className="mx-auto max-w-3xl px-6 py-12 sm:px-8 lg:px-12">
      <Link
        href={`/${lang}/reservar`}
        className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
      >
        <ArrowLeft size={16} />
        {page.back}
      </Link>

      <h1 className="mt-8 text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
        {page.title}
      </h1>
      <p className="mt-2 text-sm text-muted">{page.updated}</p>
      <div className="mt-6">
        <TextoLegal texto={page.intro} />
      </div>

      <div className="mt-12 flex flex-col gap-10 border-t border-border pt-10">
        {page.sections.map((section) => (
          <section key={section.title}>
            <h2 className="text-base font-medium tracking-tight text-foreground">{section.title}</h2>
            <div className="mt-3">
              <TextoLegal texto={section.body} />
            </div>
          </section>
          ))}
        </div>
      </main>
    </div>
  );
}
