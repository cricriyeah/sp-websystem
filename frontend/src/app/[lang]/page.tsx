import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale, type Locale } from './dictionaries';
import { LOCALE_TAG, absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { jsonLdMarca } from '@/lib/seo';
import { JsonLd } from '@/components/json-ld';
import { getSedes, type Sede } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { baseDeCobro, chipsDeSede, tarjetasConFoto } from '@/lib/etiquetas-catalogo';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { hrefSede } from '@/lib/routes';
import { ANCLA_HUB } from '@/lib/secciones-sede';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getEmpresa } from '@/content/empresas';
import type { SedeContenido } from '@/content/sedes-tipos';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { HubPortada } from '@/components/hub-portada';
import { HubMapaEscritorio } from '@/components/hub-mapa-escritorio';
import type { SedeMapa } from '@/components/hub-mapa-sedes';
import { CortinasSedes, type VistaSedeHub } from '@/components/cortinas-sedes';
import { HubComoFunciona } from '@/components/hub-como-funciona';
import { ColaboradoresSection } from '@/components/colaboradores-section';

export async function generateMetadata({ params }: PageProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return metadataDePagina({
    lang, titulo: dict.hub.meta.title, tituloCompleto: true, descripcion: dict.hub.meta.description,
    descripcionGeneral: dict.hub.meta.description, nombreDelSitio: dict.home.title,
  });
}

type Textos = Awaited<ReturnType<typeof getDictionary>>['hubContenido'];

/** Foto del panel de cada sede en el mapa: fotos genéricas de Baja del hub, nunca de las cortinas ni de la sede. */
const FOTO_MAPA: Record<string, { src: string; alt: Record<Locale, string> }> = {
  'la-paz': { src: '/sunbajaexperience/fotos/pangas-en-la-playa.webp', alt: { es: 'Pangas en la arena frente al mar', en: 'Pangas on the sand by the sea' } },
  'la-ventana': { src: '/sunbajaexperience/fotos/corriendo-a-las-olas.webp', alt: { es: 'Una persona corre hacia las olas', en: 'Someone running into the waves' } },
  'puerto-chale': { src: '/sunbajaexperience/fotos/cardon-junto-al-mar.webp', alt: { es: 'Un cardón junto al mar', en: 'A cardón cactus by the sea' } },
};

/** «Con A», «Con A y B», «Con A y N más». */
function lineaDeEmpresas(nombres: string[], textos: Textos): string | null {
  const [a, b] = nombres;
  if (!a) return null;
  if (nombres.length === 1) return textos.con1.replace('{a}', a);
  if (nombres.length === 2) return textos.con2.replace('{a}', a).replace('{b}', b);
  return textos.conN.replace('{a}', a).replace('{n}', String(nombres.length - 1));
}

/**
 * Las fotos propias de la sede para su cortina: la de la cortina (o el arranque), luego las de «Tu día» y las de
 * las temporadas, sin repetir, hasta 5. Nunca las fotos del hub.
 */
function fotosDeCortina(sede: SedeContenido): { src: string; alt: string }[] {
  const fuentes = [
    sede.hero.imagenCortina ?? sede.hero.imagen,
    ...(sede.dia?.momentos.map((momento) => momento.foto) ?? []),
    ...(sede.temporadas?.filas.map((fila) => fila.foto) ?? []),
  ].filter((src): src is string => Boolean(src));
  return [...new Set(fuentes)].slice(0, 5).map((src) => ({ src, alt: sede.nombre }));
}

/** Proyecta cada sede a lo que pinta su tarjeta. El resumen viene del backend (una sola petición). */
function vistaDeSede(sede: SedeContenido, api: Sede | undefined, conFoto: boolean, lang: Locale, textos: Textos): VistaSedeHub {
  const empresas = [sede.empresaProtagonistaSlug, ...sede.otrasEmpresas]
    .map((slug) => getEmpresa(slug)?.nombre)
    .filter((nombre): nombre is string => Boolean(nombre));
  const resumen = api?.resumen;
  const tipos = resumen?.tipos ?? [];
  const chips = chipsDeSede(
    tipos.filter((t) => t !== 'paquete').map((tipo_servicio) => ({ slug: '', tipo_servicio })),
    tipos.includes('paquete') ? [{ servicios_asociados: [] }] : [],
    lang,
  );
  const desde = resumen?.desde;
  const base = desde ? baseDeCobro(desde.base, lang) : null;
  const mxn = desde ? `${formatearPrecio(Number(desde.monto_mxn), 'MXN')} MXN` : '';
  const usd = desde ? `${formatearPrecio(Number(desde.monto_usd), 'USD')} USD` : '';
  return {
    slug: sede.slug,
    nombre: sede.nombre,
    href: hrefSede(lang, sede.slug),
    fotos: conFoto && sede.hero.imagen ? fotosDeCortina(sede) : [],
    chips,
    empresas: lineaDeEmpresas(empresas, textos),
    // En /en el USD va primero y el MXN entre paréntesis.
    desde: desde && base ? (lang === 'en' ? { monto: usd, aprox: mxn, base: base.texto } : { monto: mxn, base: base.texto }) : null,
  };
}

export default async function Home({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const sedesApi = await getSedes().catch(() => null);
  const sedes = sedesActivas(SEDES_INDICE, sedesApi).map(s => getSedeContenido(s.slug, lang)).filter((s): s is SedeContenido => !!s);
  const textos = dict.hubContenido;
  const conFoto = tarjetasConFoto(sedes);
  const vistas = sedes.map((sede) => vistaDeSede(sede, sedesApi?.find((s) => s.slug === sede.slug), conFoto, lang, textos));
  // El mapa solo orienta: dónde queda cada sede, su frase y una foto del hub; lo que se reserva y el precio
  // están en su cortina, a la que baja el botón.
  const sedesMapa: SedeMapa[] = vistas.map((vista, i) => ({
    slug: vista.slug,
    nombre: vista.nombre,
    href: `#sede-${vista.slug}`,
    subtitulo: sedes[i].hero.subtitulo,
    foto: FOTO_MAPA[vista.slug] ? { src: FOTO_MAPA[vista.slug].src, alt: FOTO_MAPA[vista.slug].alt[lang] } : null,
  }));
  const { mapAria, pacificOcean, seaOfCortez, zoomIn, zoomOut, resetMap, dragMap } = dict.hub;

  return <>
    <JsonLd datos={jsonLdMarca({
      nombre: dict.home.title, url: absolutaEn(lang), descripcion: dict.hub.meta.description, idioma: LOCALE_TAG[lang],
    })} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="hub" />
    <main>
      <HubPortada lang={lang} textos={textos} />
      <section id={ANCLA_HUB.mapa} aria-labelledby={`${ANCLA_HUB.mapa}-titulo`} className="hidden scroll-mt-[calc(var(--nav-alto)+16px)] bg-superficie py-28 lg:block">
        <div className="mx-auto max-w-[1440px] px-pagina">
          <h2 id={`${ANCLA_HUB.mapa}-titulo`} className="max-w-[24ch] texto-seccion text-foreground">{textos.mapaTitulo}</h2>
          <p className="mt-4 max-w-[60ch] texto-cuerpo text-foreground">{textos.mapaTexto}</p>
          <div className="mt-10">
            <HubMapaEscritorio sedes={sedesMapa} copy={{ mapAria, pacificOcean, seaOfCortez, zoomIn, zoomOut, resetMap, dragMap, verSede: textos.verSede }} />
          </div>
        </div>
      </section>
      <section id={ANCLA_HUB.sedes} aria-labelledby={`${ANCLA_HUB.sedes}-titulo`} className="scroll-mt-[var(--nav-alto)]">
        <h2 id={`${ANCLA_HUB.sedes}-titulo`} className="sr-only texto-seccion">{textos.sedesTitulo}</h2>
        <CortinasSedes sedes={vistas} textos={{ region: textos.region, desde: textos.desde, verSede: textos.verSede }} />
      </section>
      <HubComoFunciona id={ANCLA_HUB.comoFunciona} titulo={textos.comoTitulo} texto={textos.comoTexto} pasos={textos.comoPasos} cta={{ href: `#${ANCLA_HUB.sedes}`, etiqueta: textos.comoCta }} />
      <ColaboradoresSection id={ANCLA_HUB.empresas} sedes={sedes} lang={lang} textos={textos} />
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={null} />
  </>;
}
