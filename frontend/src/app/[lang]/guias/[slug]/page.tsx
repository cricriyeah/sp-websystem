import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound, permanentRedirect } from 'next/navigation';
import { ArrowDown, CaretRight, Check } from '@phosphor-icons/react/ssr';
import { getDictionary, hasLocale, type Locale } from '../../dictionaries';
import { GUIAS, getGuia, guiasRelacionadas, partesDeTitulo, slugEnIdioma, type DestinoGuia, type Guia, type GuiaTexto, type TemaGuia } from '@/content/guias';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getEmpresa } from '@/content/empresas';
import { getPaquetesSede, getServiciosSede } from '@/lib/api';
import { LOCALES, LOCALE_TAG, SITE_URL, absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { jsonLdArticulo, jsonLdMigas, jsonLdPreguntas } from '@/lib/seo';
import { hrefDetallePaquete, hrefGuia, hrefGuias, hrefSede, hrefServicioDetalle } from '@/lib/routes';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { JsonLd } from '@/components/json-ld';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SectionShell } from '@/components/ui/section-shell';
import { HeroMedia } from '@/components/ui/hero-media';
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { Foto } from '@/components/conocenos-sede';
import { textosDeDetalle } from '@/components/detalle-vistas';
import { TarjetaProducto, type VistaProducto } from '@/components/tarjeta-producto';
import { vistaDePaquete, vistaDeServicio } from '@/components/vistas-catalogo';
import { FaqSection } from '@/components/faq-section';
import { GuiaCalendario } from '@/components/guia-calendario';
import { TarjetasGuias } from '@/components/tarjetas-guias';

type Props = { params: Promise<{ lang: string; slug: string }> };

// El texto es fijo; lo único vivo es el precio de las tarjetas de producto, que se vuelve a pedir cada 5 minutos.
export const revalidate = 300;

export function generateStaticParams() {
  return GUIAS.flatMap((guia) => LOCALES.map((lang) => ({ lang, slug: guia.textos[lang].slug })));
}

const rutasDe = (guia: Guia): Record<Locale, string> => ({
  es: `/guias/${guia.textos.es.slug}`,
  en: `/guias/${guia.textos.en.slug}`,
});

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) return {};
  const guia = getGuia(slug, lang);
  if (!guia) return {};
  const dict = await getDictionary(lang);
  const textos = guia.textos[lang];
  return metadataDePagina({
    lang, rutas: rutasDe(guia), titulo: textos.metaTitulo, tituloCompleto: true, descripcion: textos.metaDescripcion,
    descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
  });
}

/**
 * Lo que se reserva para vivir lo que la guía explica: las tarjetas del catálogo (con su precio al día) para los
 * servicios y paquetes, y un enlace para cada sede. Si el catálogo no responde, o el producto ya no está a la venta,
 * queda el enlace a su página: la guía nunca se cae por el catálogo.
 */
async function productosDe(destinos: DestinoGuia[], lang: Locale) {
  const sedeDe = (destino: DestinoGuia) =>
    destino.tipo === 'paquete' ? destino.sede : destino.tipo === 'servicio' ? getEmpresa(destino.empresa)?.sede : undefined;
  const sedes = [...new Set(destinos.map(sedeDe).filter((sede): sede is string => Boolean(sede)))];
  const catalogos = new Map(await Promise.all(sedes.map(async (sede) => {
    const [servicios, paquetes] = await Promise.all([
      getServiciosSede(sede, lang).catch(() => null),
      getPaquetesSede(sede, lang).catch(() => null),
    ]);
    return [sede, { servicios, paquetes }] as const;
  })));

  const productos: VistaProducto[] = [];
  const enlaces: { href: string; etiqueta: string }[] = [];
  for (const destino of destinos) {
    const etiqueta = destino.etiqueta[lang];
    if (destino.tipo === 'sede') {
      enlaces.push({ href: hrefSede(lang, destino.slug), etiqueta });
      continue;
    }
    const sede = sedeDe(destino);
    const catalogo = sede ? catalogos.get(sede) : undefined;
    if (destino.tipo === 'paquete') {
      const paquete = catalogo?.paquetes?.find((p) => p.slug === destino.slug);
      if (paquete) productos.push(vistaDePaquete(paquete, lang, 'MXN'));
      else enlaces.push({ href: hrefDetallePaquete(lang, destino.sede, destino.slug), etiqueta });
    } else {
      const servicio = catalogo?.servicios?.find((s) => s.slug === destino.slug && s.empresa_slug === destino.empresa);
      if (servicio && sede) productos.push(vistaDeServicio(servicio, lang, 'MXN', sede));
      else enlaces.push({ href: hrefServicioDetalle(lang, destino.empresa, destino.slug), etiqueta });
    }
  }
  return { productos, enlaces };
}

// El color del tema, solo como acento: aquí, las palomitas de las listas. Clases completas para que Tailwind las vea.
const PALOMITA: Record<TemaGuia, string> = { mar: 'text-azul', traslado: 'text-coral-hondo', estancia: 'text-verde' };

/** Cuántas secciones van antes de la foto a sangre con la frase: la página se parte ahí para no ser una sola columna. */
const SECCIONES_ANTES_DE_LA_FRASE = 2;

/**
 * Una sección de la guía: su foto grande a un lado y la pregunta con su respuesta al otro; el lado se alterna de una
 * sección a la siguiente. En el teléfono la foto va de orilla a orilla, arriba del texto. La foto deriva dentro de su
 * marco al hacer scroll (`Foto`, la misma pieza de «Gente de mar»).
 */
function SeccionGuia({ seccion, foto, alt, alReves, tema }: {
  seccion: GuiaTexto['secciones'][number];
  foto: string | undefined;
  alt: string;
  alReves: boolean;
  tema: TemaGuia;
}) {
  return (
    <section className={cn('mx-auto grid max-w-[1440px] items-center gap-6 lg:gap-20 lg:px-pagina', foto && 'lg:grid-cols-2')}>
      {foto && (
        <Foto
          src={foto}
          alt={alt}
          sizes="(min-width: 1440px) 613px, (min-width: 1024px) 45vw, 100vw"
          rapida={alReves}
          className={cn('aspect-[4/3]', alReves && 'lg:order-2')}
        />
      )}
      <div className="px-pagina lg:px-0">
        <h2 className="rev texto-seccion">{seccion.titulo}</h2>
        <div className="mt-5 flex max-w-[56ch] flex-col gap-4 text-lg leading-relaxed">
          {seccion.parrafos.map((parrafo) => <p key={parrafo}>{parrafo}</p>)}
          {seccion.lista && (
            <ul className="flex flex-col gap-3 bg-cafe-bruma p-6">
              {seccion.lista.map((renglon) => (
                <li key={renglon} className="flex items-start gap-3">
                  <Check size={22} weight="bold" aria-hidden="true" className={cn('mt-1 shrink-0', PALOMITA[tema])} />
                  {renglon}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * Una guía, con el lenguaje de campaña del sitio: arranca con la foto a sangre y la pregunta encima, en letra grande,
 * con su respuesta; debajo, la banda negra con hasta cuatro datos; el calendario por meses; las secciones, cada una
 * con su foto grande y alternando el lado; a media página, una foto a sangre con una frase; lo que se reserva; las
 * preguntas frecuentes y más guías. El color del tema (azul = mar, coral = traslados, verde = estancia) es solo acento:
 * las casillas del calendario, las palomitas y la marca de las tarjetas (decisión del dueño, 2026-11-13).
 *
 * Quien llega de un buscador lee la respuesta antes que la marca y tiene un solo camino hacia el producto (acomodo
 * derivado con perception-first-design). Usa las piezas del sitio: `HeroMedia`, `Foto`, `SectionShell`, las tarjetas de
 * «Reserva ahora mismo» y las preguntas frecuentes. Server Component.
 */
export default async function GuiaPage({ params }: Props) {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) notFound();
  const guia = getGuia(slug, lang);
  if (!guia) {
    // El selector de idioma solo cambia `/es` por `/en`: si el slug es el de la otra versión, se lleva a la de aquí.
    const propio = slugEnIdioma(slug, lang);
    if (propio) permanentRedirect(hrefGuia(lang, propio));
    notFound();
  }
  const [dict, { productos, enlaces }] = await Promise.all([getDictionary(lang), productosDe(guia.destinos, lang)]);
  const textos = guia.textos[lang];
  const t = dict.guias;
  const sede = guia.sede ? getSedeContenido(guia.sede, lang) : undefined;
  const empresa = guia.sede ? getEmpresa(SEDES_INDICE[guia.sede]?.empresaProtagonistaSlug) : undefined;
  const url = absolutaEn(lang, rutasDe(guia)[lang]);
  const fecha = new Intl.DateTimeFormat(LOCALE_TAG[lang], { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${guia.actualizado}T00:00:00Z`));
  const textosDetalle = textosDeDetalle(dict);
  const textosFaq = dict.sedeContenido.faq;
  const whatsappFaq = tieneWhatsapp
    ? { texto: textosFaq.whatsapp, boton: textosFaq.whatsappBoton, href: whatsappHref(textosFaq.whatsappMensaje.replace('{sede}', sede?.nombre ?? t.region)) }
    : null;
  const relacionadas = guiasRelacionadas(guia);
  const titulo = partesDeTitulo(textos.titulo);
  const seccion = (i: number) => (
    <SeccionGuia
      key={textos.secciones[i].titulo}
      seccion={textos.secciones[i]}
      foto={guia.fotos[i]?.src}
      alt={guia.fotos[i]?.alt[lang] ?? ''}
      alReves={i % 2 === 1}
      tema={guia.tema}
    />
  );
  const indices = textos.secciones.map((_, i) => i);
  const cabezaProducto = (
    <div>
      <h2 id="guia-producto-titulo" className="rev texto-seccion">{textos.producto.titulo}</h2>
      <p className="mt-4 max-w-[60ch] text-lg leading-relaxed">{textos.producto.texto}</p>
    </div>
  );
  const botones = enlaces.length > 0 && (
    <ul className="flex flex-wrap gap-3">
      {enlaces.map((enlace) => (
        <li key={enlace.href}>
          <Link href={enlace.href} className={botonClases({ variante: 'campana' })}>{enlace.etiqueta}</Link>
        </li>
      ))}
    </ul>
  );

  return <>
    <JsonLd datos={[
      jsonLdArticulo({
        titulo: textos.titulo, descripcion: textos.metaDescripcion, url, imagen: `${SITE_URL}${guia.foto.src}`,
        actualizado: guia.actualizado, idioma: LOCALE_TAG[lang], editor: { nombre: dict.home.title, url: absolutaEn(lang) },
      }),
      jsonLdMigas([
        { nombre: dict.home.title, url: absolutaEn(lang) },
        { nombre: t.nombre, url: absolutaEn(lang, '/guias') },
        { nombre: textos.titulo, url },
      ]),
      jsonLdPreguntas(textos.faq),
    ]} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={guia.sede ?? undefined} />
    <main>
      <article>
        <header>
          <HeroMedia imagen={guia.foto.src} video={null} alt={guia.foto.alt[lang]} preload alto="media">
            <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-end gap-6 px-pagina pb-10 pt-[calc(var(--nav-alto)+1rem)] text-hero-ink sm:pb-14">
              <nav aria-label={t.migas} className="mb-auto">
                <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 texto-pequeno font-semibold">
                  {/* El índice es del hub: en modo «solo sede» se esconde con su flecha. */}
                  <li className="sale-al-hub flex items-center gap-2">
                    <Link href={hrefGuias(lang)} className="underline-offset-4 hover:underline">{t.nombre}</Link>
                    <CaretRight size={12} weight="bold" aria-hidden="true" />
                  </li>
                  <li>
                    {sede
                      ? <Link href={hrefSede(lang, sede.slug)} className="underline-offset-4 hover:underline">{sede.nombre}</Link>
                      : t.region}
                  </li>
                </ol>
              </nav>
              <h1 className="texto-grande">
                {titulo.principal}
                {titulo.resto && <span className="mt-3 block texto-subtitulo tracking-normal">{titulo.resto}</span>}
              </h1>
              <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
                <p className="max-w-[52ch] text-xl leading-snug">{textos.respuesta}</p>
                <a href="#guia-producto" className={botonClases({ variante: 'campana-claro' })}>
                  {textos.producto.titulo}
                  <ArrowDown size={18} weight="bold" aria-hidden="true" />
                </a>
              </div>
            </div>
          </HeroMedia>

          {/* Los datos, pegados a la foto: la letra de los titulares en blanco sobre la banda negra. */}
          <div className="bg-tinta text-hero-ink">
            <div className="mx-auto max-w-[1440px] px-pagina py-10 lg:py-14">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-4 lg:gap-x-10">
                {textos.datos.map((dato) => (
                  <div key={dato.etiqueta} className="rev flex flex-col-reverse justify-end gap-2">
                    <dt className="texto-pequeno text-hero-ink-soft">{dato.etiqueta}</dt>
                    <dd className="texto-mono-mayus text-xl font-bold leading-tight text-balance lg:text-2xl">{dato.valor}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-8 texto-pequeno text-hero-ink-soft">
                {t.actualizado.replace('{fecha}', fecha)}
                {empresa && ` · ${t.conEmpresa.replace('{empresa}', empresa.nombre)}`}
              </p>
            </div>
          </div>
        </header>

        {textos.calendario && (
          <SectionShell id="guia-calendario" fondo="cafe-bruma" titulo={textos.calendario.titulo}>
            <GuiaCalendario filas={textos.calendario.filas} idioma={LOCALE_TAG[lang]} tema={guia.tema} textos={t} />
            <p className="mt-6 max-w-[60ch] texto-cuerpo">{textos.calendario.nota}</p>
          </SectionShell>
        )}

        <div className="flex flex-col gap-16 bg-superficie py-16 sm:py-20 lg:gap-28 lg:py-28">
          {indices.slice(0, SECCIONES_ANTES_DE_LA_FRASE).map(seccion)}
        </div>

        {/* La pausa de la página: una foto a sangre con una sola frase encima. */}
        <div className="relative isolate flex min-h-[max(26rem,70svh)] flex-col justify-end overflow-clip bg-tinta text-hero-ink">
          <Image src={guia.fotoFrase.src} alt={guia.fotoFrase.alt[lang]} fill sizes="100vw" className="foto-deriva -z-10 object-cover" />
          <div aria-hidden="true" className="absolute inset-0 -z-10" style={{ background: 'var(--scrim-hero)' }} />
          <p className="mx-auto w-full max-w-[1440px] px-pagina pb-10 texto-pagina sm:pb-14">
            <span className="rev block max-w-[26ch]">{textos.frase}</span>
          </p>
        </div>

        {indices.length > SECCIONES_ANTES_DE_LA_FRASE && (
          <div className="flex flex-col gap-16 bg-superficie py-16 sm:py-20 lg:gap-28 lg:py-28">
            {indices.slice(SECCIONES_ANTES_DE_LA_FRASE).map(seccion)}
          </div>
        )}
      </article>

      {/* Lo que se reserva: un solo bloque, después de la respuesta completa. */}
      <section id="guia-producto" aria-labelledby="guia-producto-titulo" className="scroll-mt-[calc(var(--nav-alto)+16px)] bg-cafe-bruma py-16 sm:py-20 lg:py-28">
        {productos.length > 0 ? (
          <>
            <FilaArrastrable cabeza={cabezaProducto} etiqueta={t.carrilProductos} textos={textosDetalle.carril}>
              {productos.map((producto) => (
                <TarjetaProducto key={producto.clave} vista={producto} textos={textosDetalle.reservar} unica={productos.length === 1} />
              ))}
            </FilaArrastrable>
            {botones && <div className="mx-auto mt-10 max-w-[1440px] px-pagina">{botones}</div>}
          </>
        ) : (
          <div className="mx-auto max-w-[1440px] px-pagina">
            {cabezaProducto}
            {botones && <div className="mt-8">{botones}</div>}
          </div>
        )}
      </section>

      <FaqSection id="preguntas" titulo={textosFaq.titulo} preguntas={textos.faq} whatsapp={whatsappFaq} fondo="blanco" />

      {relacionadas.length > 0 && (
        <SectionShell id="guia-mas" fondo="cafe-bruma" titulo={t.masGuias}>
          <TarjetasGuias lang={lang} guias={relacionadas} className="mt-10" />
          <Link href={hrefGuias(lang)} className="sale-al-hub mt-8 inline-flex min-h-11 items-center texto-cuerpo font-semibold underline underline-offset-4">
            {t.verTodas}
          </Link>
        </SectionShell>
      )}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} />
  </>;
}
