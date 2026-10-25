// Lo que cada página le dice a los buscadores: descripciones del largo que Google muestra, etiquetas
// para compartir propias de la página y los datos estructurados (JSON-LD). Funciones puras, sin red ni
// React: el sitio las usa en `generateMetadata` y en los componentes de cada página.

/** Lo que Google suele mostrar de una descripción: unos 155 caracteres. */
export const LARGO_DESCRIPCION = 155;

/**
 * Recorta una descripción larga sin partir una palabra: en la última oración que cabe, o en la última palabra
 * con puntos suspensivos. Vacío o solo espacios devuelve `undefined` (la página usa la descripción general).
 */
export function recortarDescripcion(texto: string | null | undefined, maximo: number = LARGO_DESCRIPCION): string | undefined {
  const limpio = (texto ?? '').replace(/\s+/g, ' ').trim();
  if (!limpio) return undefined;
  if (limpio.length <= maximo) return limpio;
  const corte = limpio.slice(0, maximo);
  const finDeOracion = Math.max(corte.lastIndexOf('. '), corte.lastIndexOf('? '), corte.lastIndexOf('! '));
  if (finDeOracion >= maximo * 0.5) return corte.slice(0, finDeOracion + 1);
  const palabras = corte.slice(0, maximo - 1);
  const ultimoEspacio = palabras.lastIndexOf(' ');
  return `${(ultimoEspacio > 0 ? palabras.slice(0, ultimoEspacio) : palabras).replace(/[\s,;:.\-\u2013\u2014]+$/, '')}…`;
}

export type EntradaSocial = {
  /** URL absoluta de esta página en su idioma. */
  url: string;
  titulo: string;
  descripcion: string;
  /** `es_MX` / `en_US`. */
  locale: string;
  nombreDelSitio: string;
  /** URL absoluta de la imagen para compartir. */
  imagen: string;
};

/**
 * `openGraph` y `twitter` de una página. Next reemplaza el bloque del layout por entero cuando la página
 * define el suyo, así que se arma completo: título, descripción y URL de ESTA página (antes sedes, servicios
 * y paquetes compartían los de la portada, incluida su URL).
 */
export function etiquetasSociales({ url, titulo, descripcion, locale, nombreDelSitio, imagen }: EntradaSocial) {
  return {
    openGraph: {
      type: 'website' as const,
      url,
      siteName: nombreDelSitio,
      title: titulo,
      description: descripcion,
      locale,
      images: [{ url: imagen, width: 1200, height: 630 }],
    },
    twitter: {
      card: 'summary_large_image' as const,
      title: titulo,
      description: descripcion,
      images: [imagen],
    },
  };
}

/** `FAQPage` con las mismas preguntas que se pintan en la página. */
export function jsonLdPreguntas(preguntas: { q: string; a: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: preguntas.map((p) => ({
      '@type': 'Question',
      name: p.q,
      acceptedAnswer: { '@type': 'Answer', text: p.a },
    })),
  };
}

export type Miga = { nombre: string; url: string };

/** `BreadcrumbList`: inicio › sede › servicio o paquete. */
export function jsonLdMigas(migas: Miga[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: migas.map((miga, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: miga.nombre,
      item: miga.url,
    })),
  };
}

/**
 * La marca y el sitio, para la portada. No lleva `sameAs`, logo ni teléfono: ninguno está confirmado para la
 * marca (cada empresa tiene los suyos), y no se inventan.
 */
export function jsonLdMarca({ nombre, url, descripcion, idioma }: { nombre: string; url: string; descripcion: string; idioma: string }) {
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: nombre,
      url,
      description: descripcion,
      areaServed: { '@type': 'AdministrativeArea', name: 'Baja California Sur', addressCountry: 'MX' },
    },
    {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: nombre,
      url,
      inLanguage: idioma,
    },
  ];
}

export type EntradaViaje = {
  nombre: string;
  descripcion?: string;
  url: string;
  /** Quién presta el servicio (la empresa), no el sitio: el sitio es la vitrina. */
  proveedor: { nombre: string };
  /** Precio base en pesos, tal como lo entrega el catálogo (sin IVA). */
  precio?: string | null;
  /** Dónde ocurre: la sede. */
  lugar?: string;
};

/**
 * `TouristTrip` con su oferta. El precio del catálogo va SIN IVA y así se dice
 * (`valueAddedTaxIncluded: false`), igual que la página. Sin precio no hay oferta.
 */
export function jsonLdViaje({ nombre, descripcion, url, proveedor, precio, lugar }: EntradaViaje) {
  const importe = Number(precio);
  return {
    '@context': 'https://schema.org',
    '@type': 'TouristTrip',
    name: nombre,
    ...(descripcion ? { description: descripcion } : {}),
    url,
    provider: { '@type': 'Organization', name: proveedor.nombre },
    ...(lugar
      ? { itinerary: { '@type': 'Place', name: lugar, address: { '@type': 'PostalAddress', addressRegion: 'Baja California Sur', addressCountry: 'MX' } } }
      : {}),
    ...(Number.isFinite(importe) && importe > 0
      ? {
        offers: {
          '@type': 'Offer',
          url,
          priceCurrency: 'MXN',
          price: importe.toFixed(2),
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: importe.toFixed(2),
            priceCurrency: 'MXN',
            valueAddedTaxIncluded: false,
          },
        },
      }
      : {}),
  };
}
