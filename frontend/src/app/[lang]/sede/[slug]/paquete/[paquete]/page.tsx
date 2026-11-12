import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { cache } from 'react';
import { getDictionary, hasLocale, type Locale } from '../../../../dictionaries';
import { MedirEvento } from '@/components/medir-evento';
import { conIva } from '@/lib/iva';
import { API_URL, ApiError, getPaqueteDetalle, getPaquetesSede, getServiciosSede } from '@/lib/api';
import { sedeConVentana } from '@/lib/horario-servicio';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { claveDePaquete, fotoParaCompartir } from '@/content/imagenes-catalogo';
import { jsonLdMigas, jsonLdPreguntas, jsonLdViaje } from '@/lib/seo';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { FaqSection } from '@/components/faq-section';
import { getEmpresa } from '@/content/empresas';
import { JsonLd } from '@/components/json-ld';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { DetalleProducto } from '@/components/detalle-producto';
import { textosDeDetalle, vistaDeDetallePaquete } from '@/components/detalle-vistas';

type Props = {
  params: Promise<{ lang: string; slug: string; paquete: string }>;
  searchParams: Promise<{ moneda?: string }>;
};

const cargar = cache(async (sede: string, paquete: string, lang: Locale) => {
  try { return await getPaqueteDetalle(sede, paquete, lang); }
  catch (error) {
    // Un paquete que no existe es 404; un catálogo que no responde, no: esa página no tiene qué mostrar.
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, slug, paquete } = await params;
  if (!hasLocale(lang)) return {};
  const datos = await cargar(slug, paquete, lang).catch(() => null);
  if (!datos) return {};
  const sede = getSedeContenido(slug, lang);
  const dict = await getDictionary(lang);
  return metadataDePagina({
    lang, ruta: `/sede/${slug}/paquete/${paquete}`, titulo: sede ? `${datos.nombre} · ${sede.nombre}` : datos.nombre,
    descripcion: datos.descripcion, descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
    imagen: fotoParaCompartir(claveDePaquete(paquete))?.src,
  });
}

export default async function PaquetePage({ params, searchParams }: Props) {
  // La conexion es de fetch CORS: sin crossOrigin el navegador abriria otra.
  preconnect(API_URL, { crossOrigin: 'anonymous' });
  const { lang, slug, paquete: paqueteSlug } = await params;
  if (!hasLocale(lang)) notFound();
  const escrita = getSedeContenido(slug, lang);
  if (!escrita) notFound();
  const [paquete, query, dict, servicios, paquetes] = await Promise.all([
    cargar(slug, paqueteSlug, lang),
    searchParams,
    getDictionary(lang),
    getServiciosSede(slug, lang).catch(() => null),
    getPaquetesSede(slug, lang).catch(() => null),
  ]);
  if (!paquete) notFound();
  const sede = sedeConVentana(escrita, servicios);
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  const vista = vistaDeDetallePaquete({ lang, moneda, dict, sede, otros: { servicios, paquetes }, paquete });
  const urlPaquete = absolutaEn(lang, `/sede/${slug}/paquete/${paqueteSlug}`);
  // Las preguntas de su sede (hospedaje, horarios, cambios): las mismas que se pintan van al JSON-LD.
  const preguntas = sede.faq?.slice(0, 8);
  const textosFaq = dict.sedeContenido.faq;
  const whatsappFaq = tieneWhatsapp
    ? { texto: textosFaq.whatsapp, boton: textosFaq.whatsappBoton, href: whatsappHref(textosFaq.whatsappMensaje.replace('{sede}', paquete.nombre)) }
    : null;
  return <>
    <JsonLd datos={[
      jsonLdViaje({
        nombre: paquete.nombre, descripcion: paquete.descripcion || undefined, url: urlPaquete,
        proveedor: { nombre: getEmpresa(paquete.empresa_lider_slug)?.nombre ?? paquete.empresa_lider },
        precio: paquete.precio_ancla, lugar: sede.nombre,
      }),
      jsonLdMigas([
        { nombre: dict.home.title, url: absolutaEn(lang) },
        { nombre: sede.nombre, url: absolutaEn(lang, `/sede/${slug}`) },
        { nombre: paquete.nombre, url: urlPaquete },
      ]),
      ...(preguntas?.length ? [jsonLdPreguntas(preguntas)] : []),
    ]} />
    <MedirEvento evento="ViewContent" datos={{
      id: paquete.slug, nombre: paquete.nombre, moneda: 'MXN',
      ...(Number(paquete.precio_ancla) > 0 ? { valor: conIva(Number(paquete.precio_ancla)).total } : {}),
    }} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede.slug} />
    <main>
      <DetalleProducto vista={vista} textos={textosDeDetalle(dict)} />
      {preguntas?.length ? <FaqSection id="preguntas" titulo={textosFaq.titulo} preguntas={preguntas} whatsapp={whatsappFaq} fondo="cafe-bruma" /> : null}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede.negocio} sedeSlug={sede.slug} empresasDeslinde={[...new Set(paquete.servicios_asociados.map((c) => c.servicio.empresa_slug))]} />
  </>;
}
