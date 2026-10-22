import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { cache } from 'react';
import { getDictionary, hasLocale, type Locale } from '../../../../dictionaries';
import { API_URL, ApiError, getPaqueteDetalle, getPaquetesSede, getServiciosSede } from '@/lib/api';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { alternativasDe } from '@/lib/site';
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
  return {
    title: sede ? `${datos.nombre} · ${sede.nombre}` : datos.nombre,
    description: datos.descripcion || undefined,
    alternates: alternativasDe(lang, `/sede/${slug}/paquete/${paquete}`),
  };
}

export default async function PaquetePage({ params, searchParams }: Props) {
  // La conexion es de fetch CORS: sin crossOrigin el navegador abriria otra.
  preconnect(API_URL, { crossOrigin: 'anonymous' });
  const { lang, slug, paquete: paqueteSlug } = await params;
  if (!hasLocale(lang)) notFound();
  const sede = getSedeContenido(slug, lang);
  if (!sede) notFound();
  const [paquete, query, dict, servicios, paquetes] = await Promise.all([
    cargar(slug, paqueteSlug, lang),
    searchParams,
    getDictionary(lang),
    getServiciosSede(slug, lang).catch(() => null),
    getPaquetesSede(slug, lang).catch(() => null),
  ]);
  if (!paquete) notFound();
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  const vista = vistaDeDetallePaquete({ lang, moneda, dict, sede, otros: { servicios, paquetes }, paquete });
  return <>
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede.slug} />
    <main>
      <DetalleProducto vista={vista} textos={textosDeDetalle(dict)} />
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede.negocio} sedeSlug={sede.slug} empresasDeslinde={[...new Set(paquete.servicios_asociados.map((c) => c.servicio.empresa_slug))]} />
  </>;
}
