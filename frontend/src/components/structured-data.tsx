import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';
import { whatsappNumero, tieneWhatsapp } from '@/lib/contacto';
import { SITE_URL, absolutaEn } from '@/lib/site';
import { jsonLdNegocio, jsonLdPreguntas } from '@/lib/seo';
import { JsonLd } from './json-ld';

type StructuredDataProps = {
  lang: Locale;
  /** Slug de la sede que describe este JSON-LD — nunca el hub. */
  slug: string;
  /** Nombre de la sede: el pueblo o la ciudad donde opera la empresa. */
  localidad: string;
  /** La dirección confirmada de la empresa; `null` si todavía no la dio (va solo el pueblo). */
  negocio: SedeNegocio;
  /** La empresa protagonista de la sede: su nombre y sus perfiles confirmados. Sin ella no hay ficha de negocio. */
  empresa: { nombre: string; sameAs: readonly string[] } | null;
  /** Ruta en `public/` de la foto de la sede. */
  imagen?: string | null;
  description: string;
  faqItems: { q: string; a: string }[] | null;
};

/**
 * JSON-LD para Google: la empresa de la sede como negocio local y sus preguntas frecuentes. Sin empresa o sin
 * preguntas, el bloque correspondiente no se pinta: nada inventado.
 */
export function StructuredData({ lang, slug, localidad, negocio, empresa, imagen, description, faqItems }: StructuredDataProps) {
  const negocioJsonLd = empresa && jsonLdNegocio({
    nombre: negocio?.nombre ?? empresa.nombre,
    descripcion: description,
    url: absolutaEn(lang, `/sede/${slug}`),
    localidad: negocio?.ciudad ?? localidad,
    calle: negocio?.calle,
    telefono: tieneWhatsapp ? `+${whatsappNumero}` : undefined,
    imagen: imagen ? `${SITE_URL}${imagen}` : undefined,
    sameAs: empresa.sameAs,
  });
  const preguntasJsonLd = faqItems?.length ? jsonLdPreguntas(faqItems) : null;
  return <JsonLd datos={[negocioJsonLd, preguntasJsonLd].filter(Boolean)} />;
}
