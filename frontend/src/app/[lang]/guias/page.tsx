import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { GUIAS, guiasDeSede } from '@/content/guias';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { jsonLdMigas } from '@/lib/seo';
import { hrefSede } from '@/lib/routes';
import { JsonLd } from '@/components/json-ld';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { ListaGuias } from '@/components/lista-guias';

type Props = { params: Promise<{ lang: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return metadataDePagina({
    lang, ruta: '/guias', titulo: dict.guias.meta.title, descripcion: dict.guias.meta.description,
    descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
  });
}

/**
 * El índice de guías: el título y de qué tratan arriba, y debajo un grupo por destino (el nombre a la izquierda, sus
 * guías a la derecha, cada una con una frase que dice qué contesta) y al final las de toda la región. Mismo acomodo que
 * las preguntas frecuentes: quien llega aquí viene a escoger una, no a leer.
 *
 * Server Component, estático: todo sale de `content/guias.ts`.
 */
export default async function GuiasPage({ params }: Props) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const t = dict.guias;

  const grupos = [
    ...Object.keys(SEDES_INDICE).map((slug) => ({
      clave: slug,
      nombre: getSedeContenido(slug, lang)?.nombre ?? slug,
      href: hrefSede(lang, slug) as string | null,
      guias: guiasDeSede(slug),
    })),
    { clave: 'region', nombre: t.region, href: null, guias: GUIAS.filter((guia) => guia.sede === null) },
  ].filter((grupo) => grupo.guias.length > 0);

  return <>
    <JsonLd datos={jsonLdMigas([
      { nombre: dict.home.title, url: absolutaEn(lang) },
      { nombre: t.nombre, url: absolutaEn(lang, '/guias') },
    ])} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" />
    <main>
      <header className="bg-superficie pb-12 pt-[calc(var(--nav-alto)+1.5rem)] sm:pb-16 lg:pb-20 lg:pt-[calc(var(--nav-alto)+3.5rem)]">
        <div className="mx-auto grid max-w-[1440px] gap-6 px-pagina lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:items-end lg:gap-12">
          <h1 className="texto-seccion">{t.indiceTitulo}</h1>
          <p className="max-w-[52ch] text-xl leading-snug sm:text-2xl sm:leading-snug">{t.indiceIntro}</p>
        </div>
      </header>

      <div className="bg-cafe-bruma py-16 sm:py-20 lg:py-28">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-14 px-pagina lg:gap-20">
          {grupos.map((grupo) => (
            <section key={grupo.clave} aria-labelledby={`guias-${grupo.clave}`} className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-12">
              <h2 id={`guias-${grupo.clave}`} className="rev texto-paso">
                {grupo.href
                  ? <Link href={grupo.href} className="underline-offset-4 hover:underline">{grupo.nombre}</Link>
                  : grupo.nombre}
              </h2>
              <ListaGuias lang={lang} guias={grupo.guias} bloque="bg-superficie" resumen />
            </section>
          ))}
        </div>
      </div>
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={null} />
  </>;
}
