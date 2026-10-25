import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { cache } from 'react';
import { getDictionary, hasLocale, type Locale } from '../../../dictionaries';
import { API_URL, ApiError, getPaquetesSede, getServicioDetalle, getServiciosSede } from '@/lib/api';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { jsonLdMigas, jsonLdPreguntas, jsonLdViaje } from '@/lib/seo';
import { getFaqServicio } from '@/content/faq-servicios';
import { FaqSection } from '@/components/faq-section';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { getEmpresa } from '@/content/empresas';
import { JsonLd } from '@/components/json-ld';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { DetalleProducto } from '@/components/detalle-producto';
import { textosDeDetalle, vistaDeDetalleServicio } from '@/components/detalle-vistas';

type Props = {
  params: Promise<{ lang: string; empresa: string; servicio: string }>;
  searchParams: Promise<{ sede?: string; moneda?: string }>;
};
const cargar = cache(async (slug: string, empresa: string, lang: Locale) => {
  try { return { data: await getServicioDetalle(slug, empresa, lang), missing: false }; }
  catch (error) { return { data: null, missing: error instanceof ApiError && error.status === 404 }; }
});
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, empresa, servicio } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  const result = await cargar(servicio, empresa, lang);
  const nombre = result.data?.nombre ?? (servicio === 'pesca-deportiva' ? dict.serviceDetail.fishingTitle : dict.serviceDetail.metaFallback);
  // La sede del servicio sale de su empresa, no de `?sede=`: el buscador pide la página sin parámetros.
  const sedeDelServicio = getSedeContenido(getEmpresa(empresa)?.sede ?? '', lang);
  return metadataDePagina({
    lang, ruta: `/servicio/${empresa}/${servicio}`, titulo: sedeDelServicio ? `${nombre} · ${sedeDelServicio.nombre}` : nombre,
    descripcion: result.data?.descripcion, descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
  });
}
export default async function ServicioPage({ params, searchParams }: Props) {
  // La conexion es de fetch CORS: sin crossOrigin el navegador abriria otra.
  preconnect(API_URL, { crossOrigin: 'anonymous' });
  const { lang, empresa, servicio: slug } = await params;
  if (!hasLocale(lang)) notFound();
  const pesca = empresa === 'sal-y-sol' && slug === 'pesca-deportiva';
  // Catalogo, query y diccionario no dependen entre si: se piden a la vez.
  const [{ data: servicio, missing }, query, dict] = await Promise.all([cargar(slug, empresa, lang), searchParams, getDictionary(lang)]);
  const traslado = servicio?.tipo_servicio === 'transporte' || (empresa === 'transporte-la-paz' && slug === 'traslados-la-paz');
  if (missing && !pesca && !traslado) notFound();
  const sede = getSedeContenido(typeof query.sede === 'string' ? query.sede : 'la-paz', lang);
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  // El resto de la sede, para «También en»: si no responde, esa fila no se pinta.
  const [servicios, paquetes] = sede
    ? await Promise.all([getServiciosSede(sede.slug, lang).catch(() => null), getPaquetesSede(sede.slug, lang).catch(() => null)])
    : [null, null];
  const vista = vistaDeDetalleServicio({ lang, moneda, dict, sede, otros: { servicios, paquetes }, empresaSlug: empresa, slug, servicio, pesca, traslado });
  const sedeDelServicio = getSedeContenido(getEmpresa(empresa)?.sede ?? '', lang);
  const urlServicio = absolutaEn(lang, `/servicio/${empresa}/${slug}`);
  // Las preguntas del servicio (si ya las tiene) se pintan y van al JSON-LD: son las mismas.
  const preguntas = getFaqServicio(empresa, slug, lang);
  const textosFaq = dict.sedeContenido.faq;
  const nombreServicio = servicio?.nombre ?? dict.serviceDetail.metaFallback;
  const whatsappFaq = tieneWhatsapp
    ? { texto: textosFaq.whatsapp, boton: textosFaq.whatsappBoton, href: whatsappHref(textosFaq.whatsappMensaje.replace('{sede}', nombreServicio)) }
    : null;
  return <>
    {servicio && <JsonLd datos={[
      jsonLdViaje({
        nombre: servicio.nombre, descripcion: servicio.descripcion || undefined, url: urlServicio,
        proveedor: { nombre: getEmpresa(empresa)?.nombre ?? empresa }, precio: servicio.precio_base, lugar: sedeDelServicio?.nombre,
      }),
      jsonLdMigas([
        { nombre: dict.home.title, url: absolutaEn(lang) },
        ...(sedeDelServicio ? [{ nombre: sedeDelServicio.nombre, url: absolutaEn(lang, `/sede/${sedeDelServicio.slug}`) }] : []),
        { nombre: servicio.nombre, url: urlServicio },
      ]),
      ...(preguntas ? [jsonLdPreguntas(preguntas)] : []),
    ]} />}
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede?.slug} />
    <main>
      <DetalleProducto vista={vista} textos={textosDeDetalle(dict)} />
      {preguntas && <FaqSection id="preguntas" titulo={textosFaq.titulo} preguntas={preguntas} whatsapp={whatsappFaq} fondo="cafe-bruma" />}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} empresasDeslinde={[empresa]} />
  </>;
}
