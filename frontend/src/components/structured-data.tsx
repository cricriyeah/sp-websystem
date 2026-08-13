import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { whatsappNumero, tieneWhatsapp } from '@/lib/contacto';
import { NEGOCIO, absolutaEn } from '@/lib/site';

type StructuredDataProps = {
  lang: Locale;
  dict: Dictionary;
};

/**
 * JSON-LD para Google: ficha del negocio local y las preguntas frecuentes.
 *
 * Se arma con los mismos textos que ve el usuario — marcar datos que no estan
 * en la pagina va contra las reglas de Google y no ayuda a nadie. Faltan las
 * coordenadas del muelle a proposito: un pin mal puesto es peor que ninguno
 * (ver src/lib/site.ts).
 */
export function StructuredData({ lang, dict }: StructuredDataProps) {
  const negocio = {
    '@context': 'https://schema.org',
    '@type': 'TouristAttraction',
    name: NEGOCIO.nombre,
    description: dict.meta.home.description,
    url: absolutaEn(lang),
    address: {
      '@type': 'PostalAddress',
      streetAddress: NEGOCIO.calle,
      addressLocality: NEGOCIO.ciudad,
      addressRegion: NEGOCIO.estado,
      addressCountry: NEGOCIO.pais,
    },
    ...(tieneWhatsapp ? { telephone: `+${whatsappNumero}` } : {}),
    openingHoursSpecification: {
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
      ],
      opens: '05:00',
      closes: '07:00',
    },
    availableLanguage: ['es', 'en'],
  };

  const preguntas = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: dict.faq.items.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(negocio) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(preguntas) }}
      />
    </>
  );
}
