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
        titulo: 'Empresas locales, una experiencia compartida',
        texto1:
          'Sal y Sol Sportfishing reúne su experiencia en el mar con empresas locales de La Paz para ayudarte a organizar tu visita. Cada colaboración aporta su especialidad y el conocimiento de quienes viven aquí.',
        texto2:
          'Conoce las experiencias, paquetes y servicios de nuestros colaboradores. Puedes explorar cada opción y sus detalles antes de elegir lo que mejor se adapta a tu grupo.',
        imagenSrc: '/photos/capitan-cabrilla-bahia.webp',
        imagenAlt: 'Capitán local sonriendo con una cabrilla recién pescada, con La Paz al fondo',
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [
        { slug: 'hotel-malecon', nombre: 'Hotel Malecón', descripcion: '' },
        { slug: 'transporte-la-paz', nombre: 'Transportes La Paz', descripcion: '' },
      ],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
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
        titulo: 'Local businesses, one shared experience',
        texto1:
          'Sal y Sol Sportfishing brings its experience at sea together with local businesses in La Paz to help you plan your visit. Each partner contributes their specialty and local knowledge.',
        texto2:
          'Explore our partners’ experiences, packages and services. Read what each option includes before choosing the right experience for your group.',
        imagenSrc: '/photos/capitan-cabrilla-bahia.webp',
        imagenAlt: 'Smiling local captain holding a fresh catch, with La Paz in the background',
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [
        { slug: 'hotel-malecon', nombre: 'Hotel Malecón', descripcion: '' },
        { slug: 'transporte-la-paz', nombre: 'Transportes La Paz', descripcion: '' },
      ],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
      },
    },
  },
  'la-ventana': {
    es: {
      slug: 'la-ventana',
      empresaFundadoraSlug: null,
      negocio: null,
      metaTitle: 'Experiencias en La Ventana, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Descubre La Ventana y las experiencias que se integrarán próximamente a Sal y Sol Baja Experiences.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Descubre', emphasis: 'La Ventana', end: 'con expertos locales' },
        subtitulo:
          'Estamos preparando esta sede con operadores locales de La Ventana. Mientras completamos sus experiencias, escríbenos y te ayudamos a organizar tu visita.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Una alianza en construcción',
        texto1:
          'Estamos formalizando las colaboraciones locales que formarán parte de esta sede en La Ventana.',
        texto2:
          'Pronto podrás conocer aquí la historia completa de esta alianza, sus experiencias y su equipo.',
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Ilustración genérica de costa; imagen provisional de La Ventana',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
    en: {
      slug: 'la-ventana',
      empresaFundadoraSlug: null,
      negocio: null,
      metaTitle: 'Experiences in La Ventana, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Discover La Ventana and the experiences coming soon to Sal y Sol Baja Experiences.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Discover', emphasis: 'La Ventana', end: 'with local experts' },
        subtitulo:
          "We're preparing this destination with local operators in La Ventana. While we complete its experiences, message us and we'll help you plan your visit.",
        facts: [],
      },
      colaboracion: {
        titulo: 'A partnership in progress',
        texto1: "We're finalizing the local collaborations that will be part of this La Ventana destination.",
        texto2: "Soon you'll be able to read the full story of this partnership, its experiences, and its team here.",
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Generic coastal illustration; provisional La Ventana image',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
  },
  'puerto-chale': {
    es: {
      slug: 'puerto-chale',
      empresaFundadoraSlug: null,
      negocio: null,
      metaTitle: 'Experiencias en Puerto Chale, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Descubre Puerto Chale y las experiencias que se integrarán próximamente a Sal y Sol Baja Experiences.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Descubre', emphasis: 'Puerto Chale', end: 'con expertos locales' },
        subtitulo:
          'Estamos preparando esta sede con operadores locales de Puerto Chale. Mientras completamos sus experiencias, escríbenos y te ayudamos a organizar tu visita.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Una alianza en construcción',
        texto1:
          'Estamos formalizando las colaboraciones locales que formarán parte de esta sede en Puerto Chale.',
        texto2:
          'Pronto podrás conocer aquí la historia completa de esta alianza, sus experiencias y su equipo.',
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Ilustración genérica de costa; imagen provisional de Puerto Chale',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
    en: {
      slug: 'puerto-chale',
      empresaFundadoraSlug: null,
      negocio: null,
      metaTitle: 'Experiences in Puerto Chale, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Discover Puerto Chale and the experiences coming soon to Sal y Sol Baja Experiences.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Discover', emphasis: 'Puerto Chale', end: 'with local experts' },
        subtitulo:
          "We're preparing this destination with local operators in Puerto Chale. While we complete its experiences, message us and we'll help you plan your visit.",
        facts: [],
      },
      colaboracion: {
        titulo: 'A partnership in progress',
        texto1: "We're finalizing the local collaborations that will be part of this Puerto Chale destination.",
        texto2: "Soon you'll be able to read the full story of this partnership, its experiences, and its team here.",
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Generic coastal illustration; provisional Puerto Chale image',
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
