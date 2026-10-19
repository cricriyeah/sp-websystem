import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale, type Locale } from './dictionaries';
import { alternativasDe } from '@/lib/site';
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
import { HubGridSedes } from '@/components/hub-grid-sedes';
import { HubMapaEscritorio } from '@/components/hub-mapa-escritorio';
import type { VistaSedeHub } from '@/components/tarjeta-sede-hub';
import { HubPorQue } from '@/components/hub-por-que';
import { ColaboradoresSection } from '@/components/colaboradores-section';

export async function generateMetadata({ params }: PageProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  return { title: { absolute: dict.hub.meta.title }, description: dict.hub.meta.description, alternates: alternativasDe(lang) };
}

type Textos = Awaited<ReturnType<typeof getDictionary>>['hubContenido'];

/** «Con A», «Con A y B», «Con A y N más». */
function lineaDeEmpresas(nombres: string[], textos: Textos): string | null {
  const [a, b] = nombres;
  if (!a) return null;
  if (nombres.length === 1) return textos.con1.replace('{a}', a);
  if (nombres.length === 2) return textos.con2.replace('{a}', a).replace('{b}', b);
  return textos.conN.replace('{a}', a).replace('{n}', String(nombres.length - 1));
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
    foto: conFoto && sede.hero.imagen ? { src: sede.hero.imagen, alt: sede.nombre } : null,
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
  const sedesMapa = sedes.map((sede) => ({ slug: sede.slug, nombre: sede.nombre, empresaProtagonistaNombre: getEmpresa(sede.empresaProtagonistaSlug)?.nombre }));
  const { mapAria, pacificOcean, seaOfCortez, zoomIn, zoomOut, resetMap, dragMap, closeDestination, conLabel, verDestino } = dict.hub;

  return <>
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="hub" />
    <main>
      <HubPortada lang={lang} textos={textos} />
      <section id={ANCLA_HUB.sedes} className="scroll-mt-28 mx-auto max-w-[1440px] px-4 py-12 sm:px-6 lg:px-12">
        <h2 className="mb-8 texto-seccion">{textos.sedesTitulo}</h2>
        <HubGridSedes sedes={vistas} textos={{ region: textos.region, desde: textos.desde, verSede: textos.verSede }} />
      </section>
      <section id={ANCLA_HUB.mapa} aria-label={textos.mapaTitulo} className="hidden scroll-mt-28 mx-auto max-w-[1440px] px-12 pb-12 lg:block">
        <HubMapaEscritorio lang={lang} sedes={sedesMapa} copy={{ mapAria, pacificOcean, seaOfCortez, zoomIn, zoomOut, resetMap, dragMap, closeDestination, conLabel, verDestino }} />
      </section>
      <HubPorQue id={ANCLA_HUB.comoFunciona} headline={dict.hub.aboutTitle} pilares={dict.hub.pilares} />
      <ColaboradoresSection id={ANCLA_HUB.empresas} sedes={sedes} lang={lang} copy={dict.hub} />
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} negocio={null} />
  </>;
}
