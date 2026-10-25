import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from '../dictionaries';
import { getSedes } from '@/lib/api';
import { getEmpresa } from '@/content/empresas';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { jsonLdMigas } from '@/lib/seo';
import { hrefInicio } from '@/lib/routes';
import { ANCLA_HUB } from '@/lib/secciones-sede';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { JsonLd } from '@/components/json-ld';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { botonClases } from '@/components/ui/variantes';

const FOTO = '/sunbajaexperience/fotos/pangas-en-la-playa.webp';

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return metadataDePagina({
    lang, ruta: '/nosotros', titulo: dict.nosotros.meta.title, descripcion: dict.nosotros.meta.description,
    descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
  });
}

/**
 * Sobre nosotros: escena dividida. La foto de las pangas queda fija a un lado (en teléfono, arriba como una
 * banda) y el texto corre a su lado: primero lo que más preocupa (quién te atiende, a quién le pagas, qué pasa
 * con el clima), después cómo empezó todo y las empresas con las que trabajamos. Sin reseñas ni cifras que no
 * existen: la confianza sale de decir con claridad quién hace qué.
 *
 * Server Component.
 */
export default async function NosotrosPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const { nosotros } = dict;

  // Las empresas de las sedes que están activas hoy: la misma regla que la portada.
  const sedesApi = await getSedes().catch(() => null);
  const nombres = [...new Set(
    sedesActivas(SEDES_INDICE, sedesApi)
      .flatMap((sede) => {
        const contenido = getSedeContenido(sede.slug, lang);
        return contenido ? [contenido.empresaProtagonistaSlug, ...contenido.otrasEmpresas] : [];
      })
      .map((slug) => getEmpresa(slug)?.nombre)
      .filter((nombre): nombre is string => Boolean(nombre)),
  )];

  const [lead, ...resto] = nosotros.historia;

  return <>
    <JsonLd datos={jsonLdMigas([
      { nombre: dict.home.title, url: absolutaEn(lang) },
      { nombre: nosotros.meta.title, url: absolutaEn(lang, '/nosotros') },
    ])} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" />
    <main className="bg-background pt-[var(--nav-alto)] lg:flex">
      <div className="relative h-[42svh] w-full lg:sticky lg:top-[var(--nav-alto)] lg:h-[calc(100svh-var(--nav-alto))] lg:w-[45%] lg:shrink-0">
        <Image src={FOTO} alt={nosotros.fotoAlt} fill preload sizes="(min-width: 1024px) 45vw, 100vw" className="object-cover" />
      </div>

      <div className="flex-1 px-4 pb-20 pt-10 sm:px-6 lg:px-12 lg:pb-28 lg:pt-16">
        <div className="max-w-[44rem]">
          <h1 className="texto-display text-foreground">{nosotros.titular}</h1>
          <p className="mt-5 text-xl leading-snug text-foreground">{nosotros.subtitulo}</p>

          <section aria-labelledby="nosotros-ficha" className="mt-14">
            <h2 id="nosotros-ficha" className="texto-paso text-foreground">{nosotros.fichaTitulo}</h2>
            <dl className="mt-5 flex flex-col gap-5">
              {nosotros.ficha.map((fila) => (
                <div key={fila.etiqueta} className="grid gap-1 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6">
                  <dt className="texto-cuerpo font-semibold text-foreground">{fila.etiqueta}</dt>
                  <dd className="texto-cuerpo text-foreground">{fila.valor}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
              <Link href={hrefInicio(lang, ANCLA_HUB.sedes)} className={botonClases({ variante: 'campana' })}>
                {nosotros.cta}
              </Link>
              {tieneWhatsapp && (
                <a
                  href={whatsappHref(nosotros.whatsappMensaje)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-11 items-center texto-cuerpo font-semibold text-foreground underline underline-offset-4"
                >
                  {nosotros.whatsapp}
                </a>
              )}
            </div>
          </section>

          <section aria-labelledby="nosotros-historia" className="mt-16">
            <h2 id="nosotros-historia" className="texto-paso text-foreground">{nosotros.historiaTitulo}</h2>
            <p className="mt-5 texto-subtitulo text-foreground">{lead}</p>
            {resto.map((parrafo) => (
              <p key={parrafo} className="mt-4 max-w-[60ch] texto-cuerpo text-foreground">{parrafo}</p>
            ))}
          </section>

          {nombres.length > 0 && (
            <section aria-labelledby="nosotros-empresas" className="mt-16">
              <h2 id="nosotros-empresas" className="texto-paso text-foreground">{nosotros.empresasTitulo}</h2>
              <p className="mt-3 max-w-[60ch] texto-cuerpo text-foreground">{nosotros.empresasTexto}</p>
              <ul className="mt-5 flex flex-wrap gap-2">
                {nombres.map((nombre) => (
                  <li key={nombre} className="rounded-full bg-tinta px-4 py-2.5 texto-cuerpo font-semibold text-hero-ink">{nombre}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={null} />
  </>;
}
