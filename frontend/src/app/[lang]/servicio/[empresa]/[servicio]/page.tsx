import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { cache } from 'react';
import { getDictionary, hasLocale, type Locale } from '../../../dictionaries';
import { MedirEvento } from '@/components/medir-evento';
import { conIva } from '@/lib/iva';
import { API_URL, ApiError, getPaquetesSede, getServicioDetalle, getServiciosSede } from '@/lib/api';
import { conVentana, sedeConVentana, ventanaDeSalida } from '@/lib/horario-servicio';
import { conCatalogo, serviciosParaTexto } from '@/lib/catalogo-en-texto';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { claveDeServicio, fotoParaCompartir } from '@/content/imagenes-catalogo';
import { jsonLdMigas, jsonLdPreguntas, jsonLdViaje } from '@/lib/seo';
import { getFaqServicio } from '@/content/faq-servicios';
import { seoDeServicio } from '@/content/seo-detalle';
import { FaqSection } from '@/components/faq-section';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { getEmpresa } from '@/content/empresas';
import { JsonLd } from '@/components/json-ld';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { DetalleProducto } from '@/components/detalle-producto';
import { OpinionesEmpresas, type OpinionVista } from '@/components/opiniones-empresas';
import { FUENTE_GOOGLE, resenasMarcaDeSede } from '@/content/resenas-marca';
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
  // El título propio del servicio (lo que busca quien ya compara) o, sin él, «nombre en sede».
  const propio = seoDeServicio(empresa, servicio)?.titulo[lang];
  return metadataDePagina({
    lang, ruta: `/servicio/${empresa}/${servicio}`, tituloCompleto: Boolean(propio),
    titulo: propio ?? (sedeDelServicio ? dict.meta.servicioTitulo.replace('{nombre}', nombre).replace('{sede}', sedeDelServicio.nombre) : nombre),
    descripcion: result.data?.descripcion, descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
    imagen: fotoParaCompartir(claveDeServicio(empresa, servicio))?.src,
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
  const datosEmpresa = getEmpresa(empresa);
  // La sede donde opera la empresa: para el buscador (JSON-LD), sin importar `?sede=`.
  const sedeDelServicio = getSedeContenido(datosEmpresa?.sede ?? '', lang);
  // Sin `?sede=`, esa misma sede (no La Paz a ciegas): de ella salen el menú, el pie y el modo
  // «solo sede», que si apuntara a otra sede cambiaría de sede al cliente.
  const escrita = typeof query.sede === 'string' ? getSedeContenido(query.sede, lang) : (sedeDelServicio ?? getSedeContenido('la-paz', lang));
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  // El resto de la sede, para «También en»: si no responde, esa fila no se pinta.
  const [servicios, paquetes] = escrita
    ? await Promise.all([getServiciosSede(escrita.slug, lang).catch(() => null), getPaquetesSede(escrita.slug, lang).catch(() => null)])
    : [null, null];
  const deTexto = serviciosParaTexto(servicio ? [servicio, ...(servicios ?? [])] : servicios, paquetes);
  const sede = escrita && conCatalogo(sedeConVentana(escrita, servicios), deTexto, lang);
  // Los textos del servicio dicen su propia ventana; si la API no lo trajo, la de su sede.
  const ventana = (servicio?.pide_hora ? ventanaDeSalida(servicio.hora_apertura, servicio.hora_cierre) : null)
    ?? ventanaDeSalida(sede?.negocio?.horarioApertura, sede?.negocio?.horarioCierre);
  // Lo incluido de la pesca de Sal y Sol dice su hora y su duración del backoffice.
  const textosConHora = { ...dict, included: conCatalogo(ventana ? conVentana(dict.included, ventana) : dict.included, deTexto, lang) };
  const vista = vistaDeDetalleServicio({ lang, moneda, dict: textosConHora, sede, otros: { servicios, paquetes }, empresaSlug: empresa, slug, servicio, pesca, traslado });
  const urlServicio = absolutaEn(lang, `/servicio/${empresa}/${slug}`);
  // Las preguntas del servicio (si ya las tiene) se pintan y van al JSON-LD: son las mismas.
  // Los datos del backoffice salen del catálogo (`catalogo-en-texto`); una respuesta sin su dato no se pinta.
  const escritas = getFaqServicio(empresa, slug, lang);
  const conPrecio = escritas && conCatalogo(escritas, deTexto, lang);
  const preguntas = conPrecio && ventana ? conVentana(conPrecio, ventana) : conPrecio;
  const textosFaq = dict.sedeContenido.faq;
  const nombreServicio = servicio?.nombre ?? dict.serviceDetail.metaFallback;
  const whatsappFaq = tieneWhatsapp
    ? { texto: textosFaq.whatsapp, boton: textosFaq.whatsappBoton, href: whatsappHref(textosFaq.whatsappMensaje.replace('{sede}', nombreServicio)) }
    : null;
  // Las mismas opiniones de la sede, en el mismo componente (PFD R3): las de Google de la marca en esta sede y las
  // confirmadas de esta empresa. Sin cifra grande ni promedio (dueño, 2026-11-11).
  const marcaEnSede = sedeDelServicio ? resenasMarcaDeSede(sedeDelServicio.slug) : [];
  const opiniones: OpinionVista[] = [
    ...marcaEnSede.map((r) => ({ autor: r.autor, texto: r.texto, idioma: r.idioma, traduccion: r.traduccion, estrellas: r.estrellas, fuente: FUENTE_GOOGLE, empresa: { nombre: 'Sun Baja Experience' } })),
    ...(datosEmpresa?.resenas ?? []).filter((r) => r.confirmada).map((r) => ({
      autor: r.autor, texto: r.texto, idioma: r.idioma, fuente: r.fuente, empresa: { nombre: datosEmpresa!.nombre, logo: datosEmpresa!.logo },
    })),
  ];
  const textosFila = { anterior: dict.sedeContenido.queReservar.flechaAnterior, siguiente: dict.sedeContenido.queReservar.flechaSiguiente };
  const bloqueOpiniones = (
    <OpinionesEmpresas
      id="opiniones"
      lang={lang}
      opiniones={opiniones}
      textos={dict.sedeContenido.opiniones}
      textosFila={{ ...textosFila, pausar: dict.sedeContenido.opiniones.pausar, reanudar: dict.sedeContenido.opiniones.reanudar }}
      fondo="cafe-bruma"
      todas={marcaEnSede.length > 0 ? FUENTE_GOOGLE : undefined}
    />
  );
  return <>
    {servicio && <JsonLd datos={[
      jsonLdViaje({
        // Con el lugar: «Pesca deportiva» sola no le dice a Google de cuál se trata.
        nombre: sedeDelServicio ? dict.meta.servicioTitulo.replace('{nombre}', servicio.nombre).replace('{sede}', sedeDelServicio.nombre) : servicio.nombre,
        descripcion: servicio.descripcion || undefined, url: urlServicio,
        proveedor: { nombre: datosEmpresa?.nombre ?? empresa }, precio: servicio.precio_base, lugar: sedeDelServicio?.nombre,
      }),
      jsonLdMigas([
        { nombre: dict.home.title, url: absolutaEn(lang) },
        ...(sedeDelServicio ? [{ nombre: sedeDelServicio.nombre, url: absolutaEn(lang, `/sede/${sedeDelServicio.slug}`) }] : []),
        { nombre: servicio.nombre, url: urlServicio },
      ]),
      ...(preguntas ? [jsonLdPreguntas(preguntas)] : []),
    ]} />}
    {servicio && <MedirEvento evento="ViewContent" datos={{
      id: servicio.slug, nombre: servicio.nombre, moneda: 'MXN',
      ...(Number(servicio.precio_base) > 0 ? { valor: conIva(Number(servicio.precio_base)).total } : {}),
    }} />}
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede?.slug} />
    <main>
      <DetalleProducto
        vista={vista}
        textos={textosDeDetalle(dict)}
        opiniones={bloqueOpiniones}
        preguntas={preguntas && <FaqSection id="preguntas" titulo={textosFaq.titulo} preguntas={preguntas} whatsapp={whatsappFaq} fondo="blanco" />}
      />
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} empresasDeslinde={[empresa]} />
  </>;
}
