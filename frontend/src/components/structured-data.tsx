import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';
import { whatsappNumero, tieneWhatsapp } from '@/lib/contacto';
import { absolutaEn } from '@/lib/site';
import { JsonLd } from './json-ld';

type StructuredDataProps = {
  lang: Locale;
  /** Slug de la sede que describe este JSON-LD — nunca el hub. */
  slug: string;
  negocio: SedeNegocio;
  description: string;
  faqItems: { q: string; a: string }[] | null;
};

/**
 * JSON-LD para Google: ficha del negocio de la sede y sus preguntas
 * frecuentes. `negocio`/`faqItems` en `null` (spec §9: hoy solo pasa para
 * una sede todavía pendiente) hace que el bloque correspondiente no se renderice — sin datos
 * inventados.
 */
export function StructuredData({ lang, slug, negocio, description, faqItems }: StructuredDataProps) {
  const negocioJsonLd = negocio && {
    '@context': 'https://schema.org',
    '@type': 'TouristAttraction',
    name: negocio.nombre,
    description,
    url: absolutaEn(lang, `/sede/${slug}`),
    address: {
      '@type': 'PostalAddress',
      streetAddress: negocio.calle,
      addressLocality: negocio.ciudad,
      addressRegion: negocio.estado,
      addressCountry: negocio.pais,
    },
    ...(tieneWhatsapp ? { telephone: `+${whatsappNumero}` } : {}),
    // Sin `openingHoursSpecification`: `horarioApertura` y `horarioCierre` son la ventana de SALIDA de los viajes
    // (6 a 7 a. m.), no el horario en que el negocio atiende; publicarlo como horario decia que cierra a las 7.
    availableLanguage: ['es', 'en'],
  };

  const preguntasJsonLd = faqItems && {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqItems.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  };

  return <JsonLd datos={[negocioJsonLd, preguntasJsonLd].filter(Boolean)} />;
}
