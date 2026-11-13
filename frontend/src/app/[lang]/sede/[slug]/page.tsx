import type { Metadata } from 'next';
import { Fragment, type ReactNode } from 'react';
import { notFound, permanentRedirect } from 'next/navigation';
import { getDictionary, hasLocale } from '../../dictionaries';
import { absolutaEn } from '@/lib/site';
import { metadataDePagina } from '@/lib/metadata-pagina';
import { jsonLdMigas } from '@/lib/seo';
import { JsonLd } from '@/components/json-ld';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getEmpresa } from '@/content/empresas';
import { getPaquetesSede, getSedes, getServiciosSede, type Moneda, type ServicioCatalogo } from '@/lib/api';
import { sedeConVentana } from '@/lib/horario-servicio';
import { fotosAptas, palabrasDeSede } from '@/lib/etiquetas-catalogo';
import { tieneWhatsapp, whatsappHref, whatsappVisible } from '@/lib/contacto';
import { hrefSede } from '@/lib/routes';
import { ANCLA_DE, enlacesDeSede, fondosDeSecciones, seccionesDeSede, type SeccionId } from '@/lib/secciones-sede';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SedeHero } from '@/components/sede-hero';
import { QuePuedesReservar } from '@/components/que-puedes-reservar';
import { PaquetesSede } from '@/components/paquetes-sede';
import { DiaDeSede } from '@/components/dia-de-sede';
import { ReservaTranquila } from '@/components/reserva-tranquila';
import { ConocenosSede } from '@/components/conocenos-sede';
import { FamiliaSede } from '@/components/familia-sede';
import { PangasSede } from '@/components/pangas-sede';
import { SeasonSection } from '@/components/season-section';
import { GallerySection } from '@/components/gallery-section';
import { FaqSection } from '@/components/faq-section';
import { OpinionesEmpresas } from '@/components/opiniones-empresas';
import { FUENTE_GOOGLE, resenasMarcaDeSede } from '@/content/resenas-marca';
import { StructuredData } from '@/components/structured-data';
import type { Fondo } from '@/lib/secciones-sede';

type Props = { params: Promise<{ lang: string; slug: string }>; searchParams: Promise<{ moneda?: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) return {};
  const contenido = getSedeContenido(slug, lang);
  if (!contenido) return {};
  const dict = await getDictionary(lang);
  return metadataDePagina({
    lang, ruta: `/sede/${slug}`, titulo: contenido.metaTitle, tituloCompleto: true, descripcion: contenido.metaDescription,
    descripcionGeneral: dict.meta.home.description, nombreDelSitio: dict.home.title,
  });
}

export default async function SedePage({ params, searchParams }: Props) {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) notFound();
  if (slug === 'los-cabos') permanentRedirect(hrefSede(lang, 'la-ventana'));
  const escrito = getSedeContenido(slug, lang);
  if (!escrito) notFound();
  // Sede desactivada en el backoffice: su página deja de existir. Si la API no responde se falla abierto
  // (una caída de red no apaga el sitio), igual que el hub.
  const sedesApi = await getSedes().catch(() => null);
  if (sedesApi && !sedesApi.some((sede) => sede.slug === slug)) notFound();
  const query = await searchParams;
  const moneda: Moneda = typeof query.moneda === 'string' && query.moneda.toUpperCase() === 'USD' ? 'USD' : 'MXN';
  const [dict, paquetes, servicios] = await Promise.all([getDictionary(lang), getPaquetesSede(slug, lang).catch(() => null), getServiciosSede(slug, lang).catch(() => null)]);
  // La hora de salida de los textos es la del servicio destacado en el backoffice.
  const contenido = sedeConVentana(escrito, servicios);
  const protagonista = getEmpresa(contenido.empresaProtagonistaSlug);
  const isotipoSede = protagonista ? (protagonista.simbolo ?? protagonista.logo) : undefined;
  // Dónde va el logo largo como sello: sin `secciones`, solo en Temporadas (Sal y Sol).
  const largoEn = (seccion: 'temporadas' | 'galeria' | 'tranquilidad') =>
    (protagonista?.logoLargo?.secciones ?? ['temporadas']).includes(seccion) ? protagonista?.logoLargo : undefined;
  const marcaSede = protagonista ? { nombre: protagonista.nombre, logo: protagonista.logo, simbolo: protagonista.simbolo, simboloBarra: protagonista.simboloBarra, logoLargo: protagonista.logoLargo } : undefined;
  const empresas = [protagonista, ...contenido.otrasEmpresas.map(getEmpresa)].filter((e) => e !== undefined);
  const { temporadas } = contenido;
  // Máximo 8 preguntas: las que se pintan son las mismas que van al JSON-LD.
  const faq = contenido.faq?.slice(0, 8);
  const textosFaq = dict.sedeContenido.faq;
  const whatsappFaq = tieneWhatsapp ? { texto: textosFaq.whatsapp, boton: textosFaq.whatsappBoton, href: whatsappHref(textosFaq.whatsappMensaje.replace('{sede}', contenido.nombre)) } : null;
  // Solo las confirmadas salen del servidor: el texto de una no confirmada nunca viaja al navegador.
  // Primero las del perfil de Google de la marca (3 como máximo, sin cifra grande); luego las de cada empresa.
  const resenasMarca = resenasMarcaDeSede(slug);
  const opiniones = [
    ...resenasMarca.map((r) => ({ autor: r.autor, texto: r.texto, idioma: r.idioma, traduccion: r.traduccion, estrellas: r.estrellas, fuente: FUENTE_GOOGLE, empresa: { nombre: 'Sun Baja Experience' } })),
    ...empresas.flatMap((e) => e.resenas.filter((r) => r.confirmada).map((r) => ({
      autor: r.autor, texto: r.texto, idioma: r.idioma, fuente: r.fuente, empresa: { nombre: e.nombre, logo: e.logo },
    }))),
  ];
  // La galería no repite la foto del héroe, pero sí puede repetir las de las tarjetas (decisión del dueño,
  // 2026-10-21): una sede con pocas fotos reales no llegaría a las 3 que pide la galería. Temporadas
  // también puede repetir mientras las fotos sean de relleno (2026-10-19).
  const usadas = new Set([contenido.hero.imagen]);
  const galeria = contenido.galeria && fotosAptas(contenido.galeria.filter((foto) => !usadas.has(foto.src)));
  const empresasGaleria = Object.fromEntries((galeria ?? []).map((foto) => [foto.empresaSlug, { nombre: getEmpresa(foto.empresaSlug)?.nombre ?? foto.empresaSlug }]));

  const porcentaje = porcentajeDeSede(servicios ?? [], contenido.destacadas[0]);

  // Cada sección que sabe pintarse; `seccionesDeSede` decide cuáles van (sin reseñas confirmadas no hay opiniones).
  const pintar: Partial<Record<SeccionId, (fondo: Fondo) => ReactNode>> = {
    hero: () => <SedeHero nombre={contenido.nombre} contenido={contenido.hero} palabras={contenido.hero.palabras ?? palabrasDeSede(servicios, paquetes, lang)} empresa={marcaSede} empresaSinCirculo={protagonista?.heroSinCirculo} textos={dict.sedeContenido.arranque} />,
    ...(contenido.pangas && { pangas: (fondo: Fondo) => <PangasSede id={ANCLA_DE.pangas} pangas={contenido.pangas!} fondo={fondo} empresa={marcaSede?.nombre ?? contenido.nombre} isotipo={marcaSede?.simbolo ?? marcaSede?.logo} isotipoSinFondo={marcaSede?.simboloBarra} logoLargo={marcaSede?.logoLargo} /> }),
    reservar: (fondo) => <QuePuedesReservar lang={lang} moneda={moneda} sede={{ slug, nombre: contenido.nombre }} servicios={servicios} paquetes={paquetes} estado={secciones.find((x) => x.id === 'reservar')?.estado ?? 'normal'} destacadas={contenido.destacadas} textos={dict.sedeContenido.queReservar} fondo={fondo} presentacion={contenido.hero.presentacion} />,
    paquetes: (fondo) => <PaquetesSede id={ANCLA_DE.paquetes} lang={lang} moneda={moneda} paquetes={paquetes ?? []} textos={dict.sedeContenido.paquetes} textosReservar={dict.sedeContenido.queReservar} fondo={fondo} />,
    ...(contenido.dia && { dia: (fondo: Fondo) => <DiaDeSede id={ANCLA_DE.dia} dia={contenido.dia!} textos={{ anterior: dict.sedeContenido.queReservar.flechaAnterior, siguiente: dict.sedeContenido.queReservar.flechaSiguiente }} fondo={fondo} /> }),
    tranquilidad: (fondo) => <ReservaTranquila id={ANCLA_DE.tranquilidad} textos={dict.sedeContenido.tranquilidad} porcentaje={porcentaje} atencion={tieneWhatsapp ? { numero: whatsappVisible(), href: whatsappHref(textosFaq.whatsappMensaje.replace('{sede}', contenido.nombre)) } : null} fondo={fondo} sello={isotipoSede && protagonista ? { isotipo: isotipoSede, sinFondo: protagonista.simboloBarra, empresa: protagonista.nombre, largo: largoEn('tranquilidad') } : undefined} ilustracion={protagonista?.ilustracionFondo} />,
    ...(contenido.conocenos && { conocenos: (fondo: Fondo) => <ConocenosSede id={ANCLA_DE.conocenos} conocenos={contenido.conocenos!} fondo={fondo} logo={marcaSede?.logoLargo} empresa={marcaSede?.nombre ?? contenido.nombre} /> }),
    // Una sede lleva el «Conócenos» del gremio (La Paz) o el de una familia (Puerto Chale), nunca los dos.
    ...(!contenido.conocenos && contenido.familia && { conocenos: (fondo: Fondo) => <FamiliaSede id={ANCLA_DE.conocenos} familia={contenido.familia!} fondo={fondo} logo={marcaSede?.logoLargo} empresa={marcaSede?.nombre ?? contenido.nombre} /> }),
    ...(galeria && { galeria: (fondo: Fondo) => <GallerySection id={ANCLA_DE.galeria} titulo={dict.sedeContenido.galeria} fotos={galeria} empresas={empresasGaleria} textosVisor={dict.sedeContenido.galeriaVisor} fondo={fondo} sello={largoEn('galeria') && isotipoSede ? { isotipo: isotipoSede, sinFondo: protagonista?.simboloBarra, alt: protagonista?.nombre ?? '', largo: largoEn('galeria') } : undefined} /> }),
    ...(temporadas && { temporadas: (fondo: Fondo) => <SeasonSection id={ANCLA_DE.temporadas} titulo={temporadas.titulo ?? dict.destination.seasonsTitle} temporadas={temporadas} textos={{ ahora: dict.sedeContenido.temporadasAhora }} fondo={fondo} isotipo={isotipoSede} isotipoSinFondo={protagonista?.simboloBarra} empresa={protagonista?.nombre} logoLargo={largoEn('temporadas')} /> }),
    opiniones: (fondo) => <OpinionesEmpresas id={ANCLA_DE.opiniones} lang={lang} opiniones={opiniones} textos={dict.sedeContenido.opiniones} textosFila={{ anterior: dict.sedeContenido.queReservar.flechaAnterior, siguiente: dict.sedeContenido.queReservar.flechaSiguiente, pausar: dict.sedeContenido.opiniones.pausar, reanudar: dict.sedeContenido.opiniones.reanudar }} fondo={fondo} todas={resenasMarca.length > 0 ? FUENTE_GOOGLE : undefined} />,
    ...(faq && { preguntas: (fondo: Fondo) => <FaqSection id={ANCLA_DE.preguntas} titulo={textosFaq.titulo} preguntas={faq} whatsapp={whatsappFaq} fondo={fondo} /> }),
  };
  const secciones = seccionesDeSede({
    servicios,
    paquetes,
    resenas: [...resenasMarca.map(() => ({ confirmada: true })), ...empresas.flatMap((e) => e.resenas)],
    fotos: galeria ?? [],
    faq: faq ?? [],
    temporadas: temporadas?.filas,
    dia: contenido.dia?.momentos,
    conocenos: contenido.conocenos ? [contenido.conocenos.foto] : contenido.familia ? [contenido.familia.retrato] : undefined,
    pangas: contenido.pangas?.fotos,
  });
  const ids = secciones.map((s) => s.id).filter((id) => pintar[id]);
  const fondos = fondosDeSecciones(ids);
  const anclas = enlacesDeSede(ids).map(({ ancla, claveNav }) => ({
    ancla,
    etiqueta: (claveNav === 'temporadas' && temporadas?.nav) || dict.nav[claveNav],
  }));

  return <>
    <StructuredData lang={lang} slug={slug} negocio={contenido.negocio} description={contenido.metaDescription} faqItems={faq ?? null} />
    <JsonLd datos={jsonLdMigas([
      { nombre: dict.home.title, url: absolutaEn(lang) },
      { nombre: contenido.nombre, url: absolutaEn(lang, `/sede/${slug}`) },
    ])} />
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} variante="sede" sedeSlugActual={slug} marcaSede={marcaSede} anclas={anclas} />
    <main>
      {ids.map((id) => <Fragment key={id}>{pintar[id]?.(fondos[id] ?? 'blanco')}</Fragment>)}
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={contenido.negocio} sedeSlug={slug} anclas={anclas} empresasDeslinde={marcaSede ? [contenido.empresaProtagonistaSlug ?? ''] : []} />
  </>;
}

/**
 * El modo de pago que se cuenta en «Reserva con tranquilidad»: el anticipo del servicio destacado
 * (o, si no lo permite, el de otro servicio de la sede); `null` si todos se pagan completos.
 */
function porcentajeDeSede(servicios: ServicioCatalogo[], destacada: { tipo: string; slug: string; empresaSlug?: string } | undefined): number | null {
  const conAnticipo = (s: ServicioCatalogo) => s.permite_anticipo && s.porcentaje_anticipo > 0;
  const destacado = destacada?.tipo === 'servicio'
    ? servicios.find((s) => s.slug === destacada.slug && (!destacada.empresaSlug || s.empresa_slug === destacada.empresaSlug))
    : undefined;
  const conPorcentaje = destacado && conAnticipo(destacado) ? destacado : servicios.find(conAnticipo);
  return conPorcentaje?.porcentaje_anticipo ?? null;
}
