import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { preconnect } from 'react-dom';
import { cache } from 'react';
import { getDictionary, hasLocale } from '../../../dictionaries';
import { API_URL, ApiError, getPaquetesSede, getServicioDetalle, getServiciosSede } from '@/lib/api';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { alternativasDe } from '@/lib/site';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { DetalleProducto } from '@/components/detalle-producto';
import { textosDeDetalle, vistaDeDetalleServicio } from '@/components/detalle-vistas';

type Props = {
  params: Promise<{ lang: string; empresa: string; servicio: string }>;
  searchParams: Promise<{ sede?: string; moneda?: string }>;
};
const cargar = cache(async (slug: string, empresa: string) => {
  try { return { data: await getServicioDetalle(slug, empresa), missing: false }; }
  catch (error) { return { data: null, missing: error instanceof ApiError && error.status === 404 }; }
});
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang, empresa, servicio } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang);
  const result = await cargar(servicio, empresa);
  const title = result.data?.nombre ?? (servicio === 'pesca-deportiva' ? dict.serviceDetail.fishingTitle : dict.serviceDetail.metaFallback);
  return { title, alternates: alternativasDe(lang, `/servicio/${empresa}/${servicio}`) };
}
export default async function ServicioPage({ params, searchParams }: Props) {
  // La conexion es de fetch CORS: sin crossOrigin el navegador abriria otra.
  preconnect(API_URL, { crossOrigin: 'anonymous' });
  const { lang, empresa, servicio: slug } = await params;
  if (!hasLocale(lang)) notFound();
  const pesca = empresa === 'sal-y-sol' && slug === 'pesca-deportiva';
  // Catalogo, query y diccionario no dependen entre si: se piden a la vez.
  const [{ data: servicio, missing }, query, dict] = await Promise.all([cargar(slug, empresa), searchParams, getDictionary(lang)]);
  const traslado = servicio?.tipo_servicio === 'transporte' || (empresa === 'transporte-la-paz' && slug === 'traslados-la-paz');
  if (missing && !pesca && !traslado) notFound();
  const sede = getSedeContenido(typeof query.sede === 'string' ? query.sede : 'la-paz', lang);
  const moneda = query.moneda === 'USD' ? 'USD' : 'MXN';
  // El resto de la sede, para «También en»: si no responde, esa fila no se pinta.
  const [servicios, paquetes] = sede
    ? await Promise.all([getServiciosSede(sede.slug).catch(() => null), getPaquetesSede(sede.slug).catch(() => null)])
    : [null, null];
  const vista = vistaDeDetalleServicio({ lang, moneda, dict, sede, otros: { servicios, paquetes }, empresaSlug: empresa, slug, servicio, pesca, traslado });
  return <>
    <SiteHeader lang={lang} nav={dict.nav} continuar={dict.continuar} sedeSlugActual={sede?.slug} />
    <main>
      <DetalleProducto vista={vista} textos={textosDeDetalle(dict)} />
    </main>
    <SiteFooter lang={lang} footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.verQueReservar} negocio={sede?.negocio ?? null} sedeSlug={sede?.slug} />
  </>;
}
