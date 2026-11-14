import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound, permanentRedirect } from 'next/navigation';
import { ArrowDown, CaretRight, Check } from '@phosphor-icons/react/ssr';
import { getDictionary, hasLocale, type Locale } from '../../dictionaries';
import { GUIAS, getGuia, guiasRelacionadas, slugEnIdioma, type DestinoGuia, type Guia } from '@/content/guias';
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
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { botonClases } from '@/components/ui/variantes';
import { Cifras } from '@/components/detalle-producto';
import { textosDeDetalle } from '@/components/detalle-vistas';
import { TarjetaProducto, type VistaProducto } from '@/components/tarjeta-producto';
import { vistaDePaquete, vistaDeServicio } from '@/components/vistas-catalogo';
import { FaqSection } from '@/components/faq-section';
import { GuiaCalendario } from '@/components/guia-calendario';
import { ListaGuias } from '@/components/lista-guias';

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

/**
 * Una guía: la pregunta como título y su respuesta en la primera pantalla, con hasta cuatro datos al lado; después
 * la foto, el calendario por meses, las secciones (cada una con su pregunta), lo que se reserva y las preguntas
 * frecuentes. Las bandas alternan blanco y arena: respuesta, foto y calendario en blanco; secciones en arena; lo que se
 * reserva en blanco; preguntas en arena. Acomodo derivado con perception-first-design (2026-11-13): quien llega de un buscador lee la respuesta
 * antes que la marca, y tiene un solo camino hacia el producto.
 *
 * Usa las piezas del sitio tal cual: la ficha de datos del detalle (`Cifras`), las bandas de `SectionShell`, las
 * tarjetas de «Reserva ahora mismo» y las preguntas frecuentes. Server Component.
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
        <header className="bg-superficie pb-12 pt-[calc(var(--nav-alto)+1.5rem)] sm:pb-16 lg:pb-20 lg:pt-[calc(var(--nav-alto)+3.5rem)]">
          <div className="mx-auto grid max-w-[1440px] items-start gap-10 px-pagina lg:grid-cols-[minmax(0,1.35fr)_minmax(20rem,1fr)] lg:gap-24">
            <div>
              <nav aria-label={t.migas}>
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
              <h1 className="mt-5 texto-seccion">{textos.titulo}</h1>
              <p className="mt-6 max-w-[52ch] text-xl leading-snug sm:text-2xl sm:leading-snug">{textos.respuesta}</p>
              <a
                href="#guia-producto"
                className="mt-6 inline-flex min-h-11 items-center gap-2 texto-cuerpo font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                {textos.producto.titulo}
                <ArrowDown size={18} weight="bold" aria-hidden="true" />
              </a>
              <p className="mt-6 texto-pequeno">
                {t.actualizado.replace('{fecha}', fecha)}
                {empresa && ` · ${t.conEmpresa.replace('{empresa}', empresa.nombre)}`}
              </p>
            </div>
            <Cifras items={textos.datos} className="lg:sticky lg:top-[calc(var(--nav-alto)+1.5rem)]" />
          </div>
        </header>

        {/* La foto, de orilla a orilla en el teléfono y al ancho de la página en escritorio. */}
        <div className={textos.calendario ? 'bg-superficie' : 'bg-superficie pb-16 sm:pb-20 lg:pb-28'}>
          <div className="mx-auto max-w-[1440px] sm:px-pagina">
            <div className="rev-foto relative aspect-[4/3] overflow-hidden sm:aspect-[21/9]">
              <Image src={guia.foto.src} alt={guia.foto.alt[lang]} fill sizes="(min-width: 1440px) 1306px, 100vw" className="object-cover" />
            </div>
          </div>
        </div>

        {textos.calendario && (
          <SectionShell id="guia-calendario" fondo="blanco" titulo={textos.calendario.titulo}>
            <GuiaCalendario filas={textos.calendario.filas} idioma={LOCALE_TAG[lang]} textos={t} />
            <p className="mt-6 max-w-[60ch] texto-cuerpo">{textos.calendario.nota}</p>
          </SectionShell>
        )}

        {/* Las secciones: la pregunta a la izquierda y su respuesta a la derecha, como las preguntas frecuentes. */}
        <div className="bg-cafe-bruma py-16 sm:py-20 lg:py-28">
          <div className="mx-auto flex max-w-[1440px] flex-col gap-12 px-pagina lg:gap-16">
            {textos.secciones.map((seccion) => (
              <section key={seccion.titulo} className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-12">
                <h2 className="rev texto-paso">{seccion.titulo}</h2>
                <div className="flex max-w-[60ch] flex-col gap-4 text-lg leading-relaxed">
                  {seccion.parrafos.map((parrafo) => <p key={parrafo}>{parrafo}</p>)}
                  {seccion.lista && (
                    <ul className="flex flex-col gap-3">
                      {seccion.lista.map((renglon) => (
                        <li key={renglon} className="flex items-start gap-3">
                          <Check size={22} weight="bold" aria-hidden="true" className="mt-1 shrink-0 text-cafe" />
                          {renglon}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>
            ))}
          </div>
        </div>
      </article>

      {/* Lo que se reserva: un solo bloque, después de la respuesta completa. */}
      <section id="guia-producto" aria-labelledby="guia-producto-titulo" className="scroll-mt-[calc(var(--nav-alto)+16px)] bg-superficie py-16 sm:py-20 lg:py-28">
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

      <FaqSection id="preguntas" titulo={textosFaq.titulo} preguntas={textos.faq} whatsapp={whatsappFaq} fondo="cafe-bruma" />

      {relacionadas.length > 0 && (
        <SectionShell id="guia-mas" fondo="blanco" titulo={t.masGuias}>
          <ListaGuias lang={lang} guias={relacionadas} bloque="bg-cafe-bruma" className="mt-10" />
          <Link href={hrefGuias(lang)} className="sale-al-hub mt-8 inline-flex min-h-11 items-center texto-cuerpo font-semibold underline underline-offset-4">
            {t.verTodas}
          </Link>
        </SectionShell>
      )}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} />
  </>;
}
