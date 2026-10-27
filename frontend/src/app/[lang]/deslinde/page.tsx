import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { TextoLegal } from '@/components/texto-legal';
import { LegalBackLink } from '@/components/legal-back-link';
import { getEmpresa } from '@/content/empresas';
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

export default async function DeslindePage({ params, searchParams }: PageProps<'/[lang]/deslinde'>) {
  const [{ lang }, query] = await Promise.all([params, searchParams]);
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const { page } = dict.checkout.waiver;

  // El deslinde es de cada empresa: el texto es el mismo y lleva el nombre de la que opera la reservación
  // (`?empresa=slug`, o varios separados por comas en un paquete de dos empresas).
  const empresas = (typeof query.empresa === 'string' ? query.empresa.split(',') : [])
    .map((slug) => getEmpresa(slug))
    .filter((empresa) => empresa !== undefined);
  const nombre = empresas.length > 0 ? empresas.map((e) => e.nombre).join(lang === 'en' ? ' and ' : ' y ') : page.empresaGenerica;
  const conEmpresa = (texto: string) => texto.replaceAll('{empresa}', nombre);

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" />

      {/* SiteHeader es `fixed` y no reserva espacio: sin `--nav-alto` (ver
          globals.css) el contenido arrancaria debajo de la barra. El 3rem es
          la separacion que llevaba de siempre. */}
      <main className="mx-auto max-w-3xl px-pagina pt-[calc(3rem_+_var(--nav-alto))] pb-12">
      <LegalBackLink label={page.back} fallbackHref={`/${lang}/reservar`} />

      <h1 className="mt-8 texto-pagina text-foreground">
        {page.title}
      </h1>
      <p className="mt-2 texto-cuerpo">{page.updated}</p>
      <div className="mt-6">
        <TextoLegal texto={conEmpresa(page.intro)} />
      </div>

      <div className="mt-14 flex flex-col gap-10">
        {page.sections.map((section) => (
          <section key={section.title}>
            <h2 className="texto-subtitulo text-foreground">{section.title}</h2>
            <div className="mt-3">
              <TextoLegal texto={conEmpresa(section.body)} />
            </div>
          </section>
          ))}
        </div>
      </main>

      <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={null} empresasDeslinde={empresas.map((e) => e.slug)} />
    </div>
  );
}
