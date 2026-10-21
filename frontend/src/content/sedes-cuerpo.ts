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
      empresaProtagonistaSlug: 'sal-y-sol',
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
        subtitulo:
          'Somos una agencia local de La Paz con capitanes que conocen estas aguas como nadie. Salimos todos los días de Marina La Costa para darte la mejor experiencia de pesca en BCS.',
        facts: [
          { value: '6 a 8 horas', label: 'Duración de la aventura' },
          { value: '5:00 a 7:00 am', label: 'Horario flexible a tu gusto' },
          { value: 'Hasta 5 personas', label: 'Ambiente privado y familiar' },
          { value: '365 días al año', label: 'Salidas disponibles todo el año' },
        ],
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: ['transporte-la-paz'],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
      },
      dia: {
        titulo: 'Tu día de pesca',
        etiqueta: 'Tu día de pesca, momento por momento',
        momentos: [
          { titulo: '5:00 am', texto: 'Te espera tu capitán en Marina La Costa. Eliges la hora de salida entre 5:00 y 7:00 am.', foto: '/photos/yellowtail-pelicanos-bahia.webp' },
          { titulo: 'A bordo', texto: 'Solo tu grupo y tu capitán en la panga. Hasta 5 personas.', foto: '/photos/capitan-cabrilla-bahia.webp' },
          { titulo: 'Pesca', texto: 'De 6 a 8 horas en la bahía, buscando lo que pica en la temporada.', foto: '/photos/cana-doblada-dorado.webp' },
          { titulo: 'Regresa', texto: 'Con tus fotos y tu captura. Si reservaste traslado, DLS te lleva al hotel.', foto: '/photos/grupo-cabrilla-costa.webp' },
        ],
      },
      galeria: [
        {
          src: '/photos/dorado-bajo-toldo.webp',
          alt: 'Dorado recién subido, a la sombra del toldo',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/pesca-del-dia-cubierta.webp',
          alt: 'La pesca del día completa en la cubierta',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/marlin-en-equipo.webp',
          alt: 'Marlin capturado en equipo, listo para la foto y la liberación',
          ancho: 1448,
          alto: 1086,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/grupo-cabrilla-costa.webp',
          alt: 'Familia con su captura, cerca de la costa',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/pareja-dorados.webp',
          alt: 'Dos amigos con su dorado',
          ancho: 1448,
          alto: 1086,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/cana-doblada-dorado.webp',
          alt: 'La caña doblada, peleando un dorado',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/yellowtail-pelicanos-bahia.webp',
          alt: 'De regreso a la bahía, con pelícanos alrededor',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
      ],
      temporadas: {
        intro: 'La bahía ofrece una maravillosa variedad de especies a lo largo de las estaciones. Te compartimos nuestro calendario de pesca para ayudarte a elegir el momento ideal para tu aventura.',
        nota: 'El mar siempre nos regala momentos únicos. Nos encanta asesorarte con total honestidad sobre las condiciones y la actividad reciente; escríbenos con toda confianza por WhatsApp para platicar de cómo va la pesca esta semana.',
        etiquetaCalendario: 'Calendario de pesca mes por mes',
        etiquetaFuerte: 'Temporada fuerte',
        etiquetaOtras: 'También activas',
        filas: [
          {
            periodo: 'Diciembre a marzo',
            meses: ['Dic', 'Ene', 'Feb', 'Mar'],
            estrella: 'Jurel',
            otras: 'Sierra, cabrilla, pargo',
            nota: 'Aguas frescas y mañanas agradables. Una temporada ideal y muy divertida para toda la familia y principiantes.',
            foto: '/photos/yellowtail-pelicanos-bahia.webp',
            fuerte: false,
          },
          {
            periodo: 'Abril a junio',
            meses: ['Abr', 'May', 'Jun'],
            estrella: 'Marlin rayado',
            otras: 'Pez gallo, dorado',
            nota: 'El agua comienza a templarse y da la bienvenida a especies grandes y de gran emoción deportiva.',
            foto: '/photos/marlin-en-equipo.webp',
            fuerte: false,
          },
          {
            periodo: 'Julio a septiembre',
            meses: ['Jul', 'Ago', 'Sep'],
            estrella: 'Dorado',
            otras: 'Atún aleta amarilla, pez vela',
            nota: 'La temporada estelar de pesca deportiva. Máxima actividad y emociones garantizadas en mar abierto.',
            foto: '/photos/cana-doblada-dorado.webp',
            fuerte: true,
          },
          {
            periodo: 'Octubre a noviembre',
            meses: ['Oct', 'Nov'],
            estrella: 'Pargo',
            otras: 'Dorado, pez vela',
            nota: 'Excelente clima y gran pique, disfrutando de un ambiente muy relajado y tranquilo en la bahía.',
            foto: '/photos/pesca-del-dia-cubierta.webp',
            fuerte: false,
          },
        ],
      },
      faq: [
        {
          q: '¿Dónde veo qué incluye cada servicio?',
          a: 'Cada servicio tiene su propia lista de lo que incluye, en su tarjeta y en su página. Revísala antes de reservar; si te queda una duda, escríbenos por WhatsApp.',
        },
        {
          q: '¿Cuántas personas caben en la embarcación?',
          a: 'Contamos con dos modalidades de embarcación privada: estándar para hasta 3 personas y amplia para hasta 5 pasajeros. Toda la embarcación es 100% privada para tu grupo, garantizando comodidad y atención personalizada. Familias con niños de todas las edades son siempre bienvenidas.',
        },
        {
          q: '¿A qué hora salimos y cuánto dura?',
          a: 'Puedes elegir tu hora de salida preferida entre las 5:00 y las 7:00 am al momento de reservar. El viaje dura de 6 a 8 horas para aprovechar al máximo las mejores horas de pesca.',
        },
        {
          q: '¿Dónde nos vemos?',
          a: 'El punto de encuentro es en Marina La Costa (Rangel y Navarro, La Paz, BCS), junto al Restaurant Marina La Costa. Al reservar te enviamos la ubicación exacta y referencias, o si lo prefieres podemos cotizar y organizar tu traslado redondo.',
        },
        {
          q: '¿Cómo puedo pagar?',
          a: 'Ofrecemos modalidades cómodas y seguras: puedes liquidar el 100% en línea con tarjeta, o asegurar tu fecha con un anticipo del 30% en línea y pagar el 70% restante en efectivo el día de tu salida. Aceptamos pesos mexicanos (MXN) y dólares (USD).',
        },
        {
          q: '¿Qué pasa si hay mal clima?',
          a: 'Tu seguridad y tranquilidad son siempre nuestra máxima prioridad. Si la capitanía de puerto o nuestro capitán determinan que las condiciones del mar no son seguras, te ofrecemos reprogramar tu viaje con gusto o te reembolsamos el 100% de lo pagado.',
        },
        {
          q: '¿Puedo cambiar la fecha de mi reserva?',
          a: '¡Claro que sí! Con al menos 48 horas de anticipación podemos reprogramar tu fecha sin costo adicional según la disponibilidad. Si surge algún imprevisto con menos tiempo, avísanos cuanto antes y buscaremos con gusto la mejor solución para apoyarte.',
        },
        {
          q: '¿Necesito licencia de pesca?',
          a: 'Sí, la autoridad marítima mexicana (CONAPESCA) solicita que cada pescador a bordo cuente con su licencia individual. Es un trámite rápido por internet que toma solo unos minutos. En nuestra página te guiamos paso a paso, y nuestro equipo te asiste con gusto si necesitas apoyo.',
        },
      ],
    },
    en: {
      slug: 'la-paz',
      empresaProtagonistaSlug: 'sal-y-sol',
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
        subtitulo:
          'We are a local La Paz agency with captains who know these waters like no one else. We sail every day from Marina La Costa to bring you the best fishing experience in BCS.',
        facts: [
          { value: '6 to 8 hours', label: 'Adventure duration' },
          { value: '5:00 to 7:00 am', label: 'Flexible departure of your choice' },
          { value: 'Up to 5 guests', label: 'Private & family-friendly' },
          { value: '365 days a year', label: 'Departures available all year' },
        ],
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: ['transporte-la-paz'],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
      },
      dia: {
        titulo: 'Your fishing day',
        etiqueta: 'Your fishing day, moment by moment',
        momentos: [
          { titulo: '5:00 am', texto: 'Your captain is waiting at Marina La Costa. You choose your departure time between 5:00 and 7:00 am.', foto: '/photos/yellowtail-pelicanos-bahia.webp' },
          { titulo: 'On board', texto: 'Just your group and your captain on the boat. Up to 5 guests.', foto: '/photos/capitan-cabrilla-bahia.webp' },
          { titulo: 'Fishing', texto: 'Six to eight hours on the bay, going after whatever is biting this season.', foto: '/photos/cana-doblada-dorado.webp' },
          { titulo: 'Return', texto: 'Back with your photos and your catch. If you booked a transfer, DLS takes you to your hotel.', foto: '/photos/grupo-cabrilla-costa.webp' },
        ],
      },
      galeria: [
        {
          src: '/photos/dorado-bajo-toldo.webp',
          alt: 'Mahi just brought aboard, in the shade of the canopy',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/pesca-del-dia-cubierta.webp',
          alt: 'The day\'s full catch on deck',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/marlin-en-equipo.webp',
          alt: 'Marlin landed as a team, ready for the photo and release',
          ancho: 1448,
          alto: 1086,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/grupo-cabrilla-costa.webp',
          alt: 'Family with their catch, close to shore',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/pareja-dorados.webp',
          alt: 'Two friends with their mahi',
          ancho: 1448,
          alto: 1086,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/cana-doblada-dorado.webp',
          alt: 'Rod bent, fighting a mahi',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
        {
          src: '/photos/yellowtail-pelicanos-bahia.webp',
          alt: 'Heading back into the bay, pelicans alongside',
          ancho: 1086,
          alto: 1448,
          empresaSlug: 'sal-y-sol',
        },
      ],
      temporadas: {
        intro: 'Our bay offers an incredible variety of game fish across every season. Here is our fishing calendar to help you choose the best time for your dream adventure.',
        nota: 'Nature brings exciting new surprises every day on the water. We love sharing honest, up-to-date local insights on recent catches. Feel free to message us on WhatsApp anytime to chat about how fishing has been this week!',
        etiquetaCalendario: 'Month-by-month fishing calendar',
        etiquetaFuerte: 'Peak season',
        etiquetaOtras: 'Also active',
        filas: [
          {
            periodo: 'December to March',
            meses: ['Dec', 'Jan', 'Feb', 'Mar'],
            estrella: 'Amberjack',
            otras: 'Sierra, cabrilla, snapper',
            nota: 'Cooler waters and pleasant, calm mornings. A fantastic season for families and beginners.',
            foto: '/photos/yellowtail-pelicanos-bahia.webp',
            fuerte: false,
          },
          {
            periodo: 'April to June',
            meses: ['Apr', 'May', 'Jun'],
            estrella: 'Striped marlin',
            otras: 'Roosterfish, dorado',
            nota: 'Waters begin to warm up, welcoming exciting, high-energy sport species.',
            foto: '/photos/marlin-en-equipo.webp',
            fuerte: false,
          },
          {
            periodo: 'July to September',
            meses: ['Jul', 'Aug', 'Sep'],
            estrella: 'Dorado',
            otras: 'Yellowfin tuna, sailfish',
            nota: 'Prime sportfishing season with peak activity and thrilling offshore action.',
            foto: '/photos/cana-doblada-dorado.webp',
            fuerte: true,
          },
          {
            periodo: 'October to November',
            meses: ['Oct', 'Nov'],
            estrella: 'Snapper',
            otras: 'Dorado, sailfish',
            nota: 'Great autumn weather and fantastic bite, with peaceful conditions across the bay.',
            foto: '/photos/pesca-del-dia-cubierta.webp',
            fuerte: false,
          },
        ],
      },
      faq: [
        {
          q: 'Where can I see what each service includes?',
          a: 'Each service has its own list of what it includes, on its card and on its page. Check it before you book; if anything is unclear, message us on WhatsApp.',
        },
        {
          q: 'How many people fit on the boat?',
          a: 'We offer two private charter options: standard for up to 3 guests and large for up to 5 guests. The boat is 100% private for your group, ensuring complete comfort and personalized attention. Families with children of all ages are warmly welcome.',
        },
        {
          q: 'What time do we leave and how long is the trip?',
          a: 'You can pick your preferred departure time between 5:00 and 7:00 am when booking. The tour lasts 6 to 8 hours to take full advantage of the best morning fishing conditions.',
        },
        {
          q: 'Where do we meet?',
          a: 'We meet at Marina La Costa (Rangel & Navarro, La Paz, BCS), right by Restaurant Marina La Costa. Once booked, we\'ll send you exact location details, or we can coordinate round-trip hotel transportation for you.',
        },
        {
          q: 'How can I pay?',
          a: 'We offer convenient and secure payment options: you can pay 100% online by card, or secure your date with a 30% online deposit and settle the remaining 70% in cash on the morning of your trip. We accept MXN and USD.',
        },
        {
          q: 'What happens if the weather is bad?',
          a: 'Your safety and peace of mind are always our highest priority. If the port authority or captain determines that sea conditions are unsafe to sail, we will gladly reschedule your trip or issue a 100% full refund.',
        },
        {
          q: 'Can I change my booking date?',
          a: 'Yes, absolutely! With at least 48 hours notice, we can reschedule your trip at no extra charge according to availability. If an unexpected change happens closer to your date, let us know right away and we\'ll do our best to find a great solution.',
        },
        {
          q: 'Do I need a fishing licence?',
          a: 'Yes, Mexican regulations (CONAPESCA) require each angler on board to hold an individual sportfishing permit. It is a quick online process taking just a few minutes. We provide a step-by-step guide on our site, and our team will gladly assist you if needed.',
        },
      ],
    },
  },
  'la-ventana': {
    es: {
      slug: 'la-ventana',
      empresaProtagonistaSlug: 'la-ventana-travel',
      negocio: null,
      metaTitle: 'Experiencias en La Ventana, BCS | Sun Baja Experience',
      metaDescription:
        'Explora la pesca con mosca, el avistamiento de ballenas y orcas y los paquetes de La Ventana Travel.',
      hero: {
        video: '/videos/videohero.webm', // relleno hasta el video propio
        imagen: '/photos/mar-poster.webp',
        subtitulo:
          'Explora la pesca con mosca, el avistamiento de ballenas y orcas y los paquetes con hospedaje de La Ventana Travel.',
        facts: [],
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
    en: {
      slug: 'la-ventana',
      empresaProtagonistaSlug: 'la-ventana-travel',
      negocio: null,
      metaTitle: 'Experiences in La Ventana, BCS | Sun Baja Experience',
      metaDescription:
        'Explore fly fishing, whale and orca watching, and multi-day packages with La Ventana Travel.',
      hero: {
        video: '/videos/videohero.webm', // relleno hasta el video propio
        imagen: '/photos/mar-poster.webp',
        subtitulo:
          'Explore fly fishing, whale and orca watching, and packages with lodging from La Ventana Travel.',
        facts: [],
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
  },
  'puerto-chale': {
    es: {
      slug: 'puerto-chale',
      empresaProtagonistaSlug: 'piratas-adventures',
      negocio: null,
      metaTitle: 'Experiencias en Puerto Chale, BCS | Sun Baja Experience',
      metaDescription:
        'Explora el safari marino, el avistamiento de ballenas y la pesca deportiva de Piratas Adventures en Puerto Chale.',
      hero: {
        video: '/videos/videohero.webm', // relleno hasta el video propio
        imagen: '/photos/mar-poster.webp',
        subtitulo:
          'Explora el safari marino, el avistamiento de ballenas y la pesca deportiva de Piratas Adventures en Puerto Chale.',
        facts: [],
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
    en: {
      slug: 'puerto-chale',
      empresaProtagonistaSlug: 'piratas-adventures',
      negocio: null,
      metaTitle: 'Experiences in Puerto Chale, BCS | Sun Baja Experience',
      metaDescription:
        'Explore marine safaris, whale watching, and sportfishing with Piratas Adventures in Puerto Chale.',
      hero: {
        video: '/videos/videohero.webm', // relleno hasta el video propio
        imagen: '/photos/mar-poster.webp',
        subtitulo:
          'Explore marine safaris, whale watching, and sportfishing with Piratas Adventures in Puerto Chale.',
        facts: [],
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
