import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { Warning, ArrowLeft, WhatsappLogo } from '@phosphor-icons/react/ssr';
import { getDictionary, hasLocale } from '../dictionaries';
import { getTraslados } from '@/lib/api';
import { alternativasDe } from '@/lib/site';
import { whatsappHref, tieneWhatsapp } from '@/lib/contacto';
import { SiteHeader } from '@/components/site-header';
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
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;

  const empresaSlug =
    typeof query.empresa === 'string' && query.empresa
      ? query.empresa
      : (process.env.NEXT_PUBLIC_TRANSPORTE_EMPRESA_SLUG ?? 'transporte-la-paz');

  const catalogo = await getTraslados(empresaSlug).catch(() => null);

  if (!catalogo || !catalogo.servicio) {
    return (
      <div className="min-h-dvh bg-surface">
        <SiteHeader lang={lang} nav={dict.nav} />
        <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
          <Link
            href={`/${lang}/catalogo`}
            className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
          >
            <ArrowLeft size={16} />
            {dict.traslados.back}
          </Link>
        </div>

        <main className="mx-auto max-w-2xl px-6 py-16 text-center sm:px-8">
          <div className="rounded-2xl border border-border bg-background p-8 shadow-sm sm:p-12">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-accent/10 text-accent">
              <Warning size={32} />
            </div>
            <h1 className="mt-6 text-2xl font-bold tracking-tight text-foreground">
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
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-action px-6 py-3 text-sm font-semibold text-action-foreground shadow-sm transition-transform active:scale-[0.98]"
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
          bookLabel={dict.booking.submit}
          negocio={null}
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
    />
  );
}
