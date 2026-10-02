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
        { slug: 'transporte-la-paz', nombre: 'DLS Transporte', descripcion: '' },
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
        { slug: 'transporte-la-paz', nombre: 'DLS Transporte', descripcion: '' },
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
        'Explora la pesca con mosca, el avistamiento de ballenas y orcas y los paquetes de La Ventana Travel.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Descubre', emphasis: 'La Ventana', end: 'con expertos locales' },
        subtitulo:
          'Explora la pesca con mosca, el avistamiento de ballenas y orcas y los paquetes con hospedaje de La Ventana Travel.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Experiencias con operadores locales',
        texto1:
          'La Ventana Travel reúne experiencias en el mar y paquetes de varios días en La Ventana.',
        texto2:
          'Consulta los servicios y paquetes disponibles para elegir el viaje que se adapte a tu grupo.',
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Ilustración genérica de costa; imagen provisional de La Ventana',
      },
      destacadas: [],
      otrasEmpresas: [
        { slug: 'la-ventana-travel', nombre: 'La Ventana Travel', descripcion: '' },
      ],
      servicioTransporte: null,
    },
    en: {
      slug: 'la-ventana',
      empresaFundadoraSlug: null,
      negocio: null,
      metaTitle: 'Experiences in La Ventana, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Explore fly fishing, whale and orca watching, and multi-day packages with La Ventana Travel.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Discover', emphasis: 'La Ventana', end: 'with local experts' },
        subtitulo:
          'Explore fly fishing, whale and orca watching, and packages with lodging from La Ventana Travel.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Experiences with local operators',
        texto1: 'La Ventana Travel brings together sea experiences and multi-day packages in La Ventana.',
        texto2: 'Explore the available services and packages to find a trip that fits your group.',
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Generic coastal illustration; provisional La Ventana image',
      },
      destacadas: [],
      otrasEmpresas: [
        { slug: 'la-ventana-travel', nombre: 'La Ventana Travel', descripcion: '' },
      ],
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
        'Explora el safari marino, el avistamiento de ballenas y la pesca deportiva de Piratas Adventures en Puerto Chale.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Descubre', emphasis: 'Puerto Chale', end: 'con expertos locales' },
        subtitulo:
          'Explora el safari marino, el avistamiento de ballenas y la pesca deportiva de Piratas Adventures en Puerto Chale.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Experiencias con operadores locales',
        texto1:
          'Piratas Adventures ofrece salidas al mar y pesca deportiva en Puerto Chale.',
        texto2:
          'Consulta los servicios disponibles y elige la experiencia que se adapte a tu grupo.',
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Ilustración genérica de costa; imagen provisional de Puerto Chale',
      },
      destacadas: [],
      otrasEmpresas: [
        { slug: 'piratas-adventures', nombre: 'Piratas Adventures', descripcion: '' },
      ],
      servicioTransporte: null,
    },
    en: {
      slug: 'puerto-chale',
      empresaFundadoraSlug: null,
      negocio: null,
      metaTitle: 'Experiences in Puerto Chale, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Explore marine safaris, whale watching, and sportfishing with Piratas Adventures in Puerto Chale.',
      hero: {
        video: null,
        imagen: '/ilustraciones/costa-placeholder.webp',
        titulo: { start: 'Discover', emphasis: 'Puerto Chale', end: 'with local experts' },
        subtitulo:
          'Explore marine safaris, whale watching, and sportfishing with Piratas Adventures in Puerto Chale.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Experiences with local operators',
        texto1: 'Piratas Adventures offers sea outings and sportfishing in Puerto Chale.',
        texto2: 'Explore the available services and choose an experience that fits your group.',
        imagenSrc: '/ilustraciones/costa-placeholder.webp',
        imagenAlt: 'Generic coastal illustration; provisional Puerto Chale image',
      },
      destacadas: [],
      otrasEmpresas: [
        { slug: 'piratas-adventures', nombre: 'Piratas Adventures', descripcion: '' },
      ],
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
