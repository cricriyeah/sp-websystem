import { redirect } from 'next/navigation';
import { notFound } from 'next/navigation';
import { hasLocale } from '../dictionaries';
import { getSedeIndice } from '@/content/sedes-indice';

type PageProps = {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

/**
 * `/catalogo` ya no tiene contenido propio (spec §9): el selector de sede y
 * los grids de paquetes/servicios viven ahora en el hub y en la pagina de
 * sede. Este stub solo redirige a donde corresponda, para no romper links
 * viejos/externos que todavia apunten aqui.
 */
export default async function CatalogoRedirectPage({ params, searchParams }: PageProps) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const query = await searchParams;
  const sedeQuery = typeof query.sede === 'string' ? query.sede : undefined;
  const existe = sedeQuery ? getSedeIndice(sedeQuery) : undefined;

  redirect(existe ? `/${lang}/sede/${sedeQuery}` : `/${lang}`);
}
