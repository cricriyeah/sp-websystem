// frontend/src/content/sedes-cuerpo.ts
import 'server-only';
import type { Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from './sedes-indice';
import type { SedeCuerpoContenido, SedeContenido } from './sedes-tipos';

/**
 * Contenido largo por sede, bilingue. `server-only`: si algun componente
 * cliente lo importa por error, el build falla en vez de mandar estos
 * parrafos al bundle de cliente sin que nadie los necesite ahi.
 */
export const SEDES_CUERPO: Record<string, Record<Locale, SedeCuerpoContenido>> = {
  'la-paz': {
    es: {
      slug: 'la-paz',
      empresaFundadoraSlug: 'sal-y-sol',
      negocio: {
        nombre: 'Sal y Sol Sportfishing',
        calle: 'Marina La Costa, Rangel y Navarro',
        ciudad: 'La Paz',
        estado: 'Baja California Sur',
        pais: 'MX',
        horarioApertura: '05:00',
        horarioCierre: '07:00',
      },
      metaTitle: 'Tours de pesca deportiva en La Paz, BCS | Sal y Sol Sportfishing',
      metaDescription:
        'Vive la mejor experiencia de pesca deportiva en La Paz, BCS con capitanes locales. Salidas privadas desde Marina La Costa. Reserva en línea o escríbenos por WhatsApp.',
      hero: {
        video: '/videos/videohero.webm',
        imagen: '/photos/cola-amarilla-acantilado.webp',
        titulo: { start: 'Ven a pescar', emphasis: 'con nosotros', end: 'a la Bahía de La Paz' },
        subtitulo:
          'Somos una agencia local de La Paz con capitanes que conocen estas aguas como nadie. Salimos todos los días de Marina La Costa para darte la mejor experiencia de pesca en BCS.',
        facts: [
          { value: '6 a 8 horas', label: 'Duración de la aventura' },
          { value: '5:00 a 7:00 am', label: 'Horario flexible a tu gusto' },
          { value: 'Hasta 5 personas', label: 'Ambiente privado y familiar' },
          { value: '365 días al año', label: 'Salidas disponibles todo el año' },
        ],
      },
      colaboracion: {
        titulo: 'Tu agencia local de confianza: apasionados por el mar y por tu experiencia',
        texto1:
          'Somos una agencia de pesca deportiva conformada por gente local que conoce, respeta y ama profundamente las aguas de La Paz. Nos preocupamos por cada detalle de tu viaje para que tú y tu grupo disfruten de una jornada extraordinaria, sintiéndose en confianza y con la calidez que nos distingue.',
        texto2:
          'Cada tour es 100% privado y pensado a la medida de tu grupo. Si es tu primera vez en la pesca deportiva, nuestros capitanes te enseñarán con paciencia y gusto las mejores técnicas, y si ya eres un pescador experimentado, te llevaremos a los mejores puntos de la bahía para maximizar tus capturas.',
        imagenSrc: '/photos/capitan-cabrilla-bahia.webp',
        imagenAlt: 'Capitán local sonriendo con una cabrilla recién pescada, con La Paz al fondo',
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
        hrefTraslados: '/traslados?empresa=transporte-la-paz',
      },
    },
    en: {
      slug: 'la-paz',
      empresaFundadoraSlug: 'sal-y-sol',
      negocio: {
        nombre: 'Sal y Sol Sportfishing',
        calle: 'Marina La Costa, Rangel y Navarro',
        ciudad: 'La Paz',
        estado: 'Baja California Sur',
        pais: 'MX',
        horarioApertura: '05:00',
        horarioCierre: '07:00',
      },
      metaTitle: 'Sportfishing Charters in La Paz, BCS | Sal y Sol Sportfishing',
      metaDescription:
        'Experience the best sportfishing in La Paz, BCS with passionate local captains. Private charters from Marina La Costa. Book online or message us on WhatsApp.',
      hero: {
        video: '/videos/videohero.webm',
        imagen: '/photos/cola-amarilla-acantilado.webp',
        titulo: { start: 'Come fishing', emphasis: 'with us', end: 'in the Bay of La Paz' },
        subtitulo:
          'We are a local La Paz agency with captains who know these waters like no one else. We sail every day from Marina La Costa to bring you the best fishing experience in BCS.',
        facts: [
          { value: '6 to 8 hours', label: 'Adventure duration' },
          { value: '5:00 to 7:00 am', label: 'Flexible departure of your choice' },
          { value: 'Up to 5 guests', label: 'Private & family-friendly' },
          { value: '365 days a year', label: 'Departures available all year' },
        ],
      },
      colaboracion: {
        titulo: 'Your trusted local agency: passionate about the sea and your experience',
        texto1:
          'We are a local sportfishing agency based in La Paz, run by local experts who deeply know, respect, and love these waters. We take care of every detail of your charter so that you and your party feel welcomed, supported, and free to enjoy an extraordinary day out on the sea.',
        texto2:
          'Every trip is 100% private and tailored to your group. Whether you are holding a fishing rod for the very first time or are a seasoned angler, our friendly captains will guide you with patience, warmth, and skill, taking you to the most productive spots in the bay for an unforgettable adventure.',
        imagenSrc: '/photos/capitan-cabrilla-bahia.webp',
        imagenAlt: 'Smiling local captain holding a fresh catch, with La Paz in the background',
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
        hrefTraslados: '/traslados?empresa=transporte-la-paz',
      },
    },
  },
  'los-cabos': {
    es: {
      slug: 'los-cabos',
      empresaFundadoraSlug: 'tours-cabo',
      negocio: null,
      metaTitle: 'Experiencias en Los Cabos, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Descubre las experiencias de Tours Cabo en Los Cabos, aliado de Sal y Sol Baja Experiences.',
      hero: {
        video: null,
        imagen: '/ilustraciones/los-cabos-placeholder.webp',
        titulo: { start: 'Descubre', emphasis: 'Los Cabos', end: 'con Tours Cabo' },
        subtitulo:
          'Tours Cabo es nuestro aliado local en Los Cabos. Estamos completando el contenido de esta sede — mientras tanto, escríbenos y te ayudamos igual.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Una alianza en construcción',
        texto1:
          'Estamos formalizando el contenido de esta colaboración con Tours Cabo, nuestro aliado en Los Cabos.',
        texto2:
          'Pronto podrás conocer aquí la historia completa de esta alianza, sus experiencias y su equipo.',
        imagenSrc: '/ilustraciones/los-cabos-placeholder.webp',
        imagenAlt: 'Ilustración genérica de costa; imagen provisional de Los Cabos',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
    en: {
      slug: 'los-cabos',
      empresaFundadoraSlug: 'tours-cabo',
      negocio: null,
      metaTitle: 'Experiences in Los Cabos, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Discover Tours Cabo experiences in Los Cabos, a Sal y Sol Baja Experiences partner.',
      hero: {
        video: null,
        imagen: '/ilustraciones/los-cabos-placeholder.webp',
        titulo: { start: 'Discover', emphasis: 'Los Cabos', end: 'with Tours Cabo' },
        subtitulo:
          "Tours Cabo is our local partner in Los Cabos. We're still completing this destination's content — message us in the meantime and we'll help all the same.",
        facts: [],
      },
      colaboracion: {
        titulo: 'A partnership in progress',
        texto1: "We're finalizing the content for this collaboration with Tours Cabo, our partner in Los Cabos.",
        texto2: "Soon you'll be able to read the full story of this partnership, its experiences, and its team here.",
        imagenSrc: '/ilustraciones/los-cabos-placeholder.webp',
        imagenAlt: 'Generic coastal illustration; provisional Los Cabos image',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
  },
};

export function getSedeCuerpo(slug: string, lang: Locale): SedeCuerpoContenido | undefined {
  return SEDES_CUERPO[slug]?.[lang];
}

/** Combina indice + cuerpo. La forma completa que consumen las paginas de servidor. */
export function getSedeContenido(slug: string, lang: Locale): SedeContenido | undefined {
  const indice = Object.hasOwn(SEDES_INDICE, slug) ? SEDES_INDICE[slug] : undefined;
  const cuerpo = SEDES_CUERPO[slug]?.[lang];
  if (!indice || !cuerpo) return undefined;
  return { ...indice, ...cuerpo };
}
