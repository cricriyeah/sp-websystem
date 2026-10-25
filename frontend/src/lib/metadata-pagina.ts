import type { Metadata } from 'next';
import type { Locale } from '@/app/[lang]/dictionaries';
import { LOCALE_TAG, absolutaEn, alternativasDe } from './site';
import { etiquetasSociales, recortarDescripcion } from './seo';

type Entrada = {
  lang: Locale;
  /** Ruta de la página sin idioma (`/sede/la-paz`); vacía para la portada. */
  ruta?: string;
  titulo: string;
  /** El título ya lleva la marca: no se le agrega «| Sun Baja Experience». */
  tituloCompleto?: boolean;
  descripcion: string | null | undefined;
  /** La descripción de la portada: la que se usa si la página no tiene una propia. */
  descripcionGeneral: string;
  /** «Sun Baja Experience». */
  nombreDelSitio: string;
};

/**
 * El metadata completo de una página: título, descripción del largo que muestra Google, canonical, hreflang
 * y las etiquetas para compartir de ESA página (no las de la portada). Next reemplaza `openGraph` y `twitter`
 * del layout cuando la página define los suyos, por eso aquí se arman enteros, con la imagen del sitio.
 */
export function metadataDePagina({
  lang, ruta = '', titulo, tituloCompleto = false, descripcion, descripcionGeneral, nombreDelSitio,
}: Entrada): Metadata {
  const descripcionFinal = recortarDescripcion(descripcion) ?? descripcionGeneral;
  const tituloSocial = tituloCompleto ? titulo : `${titulo} | ${nombreDelSitio}`;
  return {
    title: tituloCompleto ? { absolute: titulo } : titulo,
    description: descripcionFinal,
    alternates: alternativasDe(lang, ruta),
    ...etiquetasSociales({
      url: absolutaEn(lang, ruta),
      titulo: tituloSocial,
      descripcion: descripcionFinal,
      locale: LOCALE_TAG[lang].replace('-', '_'),
      nombreDelSitio,
      imagen: absolutaEn(lang, '/opengraph-image'),
    }),
  };
}
