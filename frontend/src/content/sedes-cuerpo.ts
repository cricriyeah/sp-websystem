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
        palabras: ['Pesca', 'Dorado', 'Marlín', 'Jurel', 'Mar', 'Aventura', 'Sal y Sol'],
        subtitulo:
          'Somos una agencia local de La Paz con capitanes que conocen estas aguas como nadie. Salimos todos los días de Marina La Costa para darte la mejor experiencia de pesca en BCS.',
        facts: [
          { value: '6 a 7 horas', label: 'Duración de la aventura' },
          { value: '5:00 a 7:00 am', label: 'Horario flexible a tu gusto' },
          { value: 'Hasta 5 personas', label: 'Ambiente privado y familiar' },
          { value: '365 días al año', label: 'Salidas disponibles todo el año' },
        ],
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [], // DLS Transporte está desactivado por ahora
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
      },
      dia: {
        titulo: 'Tu día de pesca',
        etiqueta: 'Tu día de pesca, momento por momento',
        momentos: [
          { titulo: '5:00 am', texto: 'Te espera tu capitán en Marina La Costa. Eliges la hora de salida entre 5:00 y 7:00 am.', foto: '/photos/yellowtail-pelicanos-bahia.webp' },
          { titulo: 'A bordo', texto: 'Solo tu grupo y tu capitán en la panga. Hasta 5 personas.', foto: '/photos/capitan-cabrilla-bahia.webp' },
          { titulo: 'Pesca', texto: 'De 6 a 7 horas en la bahía, buscando lo que pica en la temporada.', foto: '/photos/cana-doblada-dorado.webp' },
          { titulo: 'Regresa', texto: 'Con tus fotos y tu captura.', foto: '/photos/grupo-cabrilla-costa.webp' },
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
        etiquetaCalendario: 'Calendario de pesca mes por mes',
        etiquetaFuerte: 'Temporada fuerte',
        etiquetaOtras: 'También activas',
        filas: [
          {
            periodo: 'Enero a abril',
            meses: ['Ene', 'Feb', 'Mar', 'Abr'],
            estrella: 'Jurel',
            descripcion: 'Aguas frescas y mar tranquilo: temporada de peleas largas con el jurel, ideal para quien quiere pescar con calma.',
            otras: 'Pargo, cabrilla',
            foto: '/photos/yellowtail-pelicanos-bahia.webp',
            fuerte: false,
          },
          {
            periodo: 'Junio a octubre',
            meses: ['Jun', 'Jul', 'Ago', 'Sep', 'Oct'],
            estrella: 'Marlin y dorado',
            descripcion: 'El mar caliente trae a los grandes: la temporada con más acción para quien busca una pelea de las que se cuentan.',
            otras: '',
            foto: '/photos/cana-doblada-dorado.webp',
            fuerte: true,
          },
          {
            periodo: 'Noviembre a diciembre',
            meses: ['Nov', 'Dic'],
            estrella: 'Sierra',
            descripcion: 'El final del año deja pesca constante y buen clima para salir temprano, con la sierra como protagonista.',
            otras: 'Cochito',
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
          a: 'Puedes elegir tu hora de salida preferida entre las 5:00 y las 7:00 am al momento de reservar. El viaje dura de 6 a 7 horas para aprovechar al máximo las mejores horas de pesca.',
        },
        {
          q: '¿Dónde nos vemos?',
          a: 'El punto de encuentro es en Marina La Costa (Rangel y Navarro, La Paz, BCS), junto al Restaurant Marina La Costa. Al reservar te enviamos la ubicación exacta y referencias. Si lo prefieres, puedes reservar también un traslado redondo a la actividad con nuestro paquete de pesca y traslado.',
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
          a: 'Sí, la autoridad marítima mexicana (CONAPESCA) solicita que cada pescador a bordo cuente con su licencia individual. Puedes agregar el trámite de la licencia a tu viaje y nosotros la tramitamos por ti con gusto.',
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
        palabras: ['Fishing', 'Mahi', 'Marlin', 'Yellowtail', 'Sea', 'Adventure', 'Sal y Sol'],
        subtitulo:
          'We are a local La Paz agency with captains who know these waters like no one else. We sail every day from Marina La Costa to bring you the best fishing experience in BCS.',
        facts: [
          { value: '6 to 7 hours', label: 'Adventure duration' },
          { value: '5:00 to 7:00 am', label: 'Flexible departure of your choice' },
          { value: 'Up to 5 guests', label: 'Private & family-friendly' },
          { value: '365 days a year', label: 'Departures available all year' },
        ],
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [], // DLS Transporte está desactivado por ahora
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
          { titulo: 'Return', texto: 'Back with your photos and your catch.', foto: '/photos/grupo-cabrilla-costa.webp' },
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
        etiquetaCalendario: 'Month-by-month fishing calendar',
        etiquetaFuerte: 'Peak season',
        etiquetaOtras: 'Also active',
        filas: [
          {
            periodo: 'January to April',
            meses: ['Jan', 'Feb', 'Mar', 'Apr'],
            estrella: 'Amberjack',
            descripcion: 'Cool water and calm seas: a season of long fights with amberjack, ideal if you want to fish at an easy pace.',
            otras: 'Snapper, cabrilla',
            foto: '/photos/yellowtail-pelicanos-bahia.webp',
            fuerte: false,
          },
          {
            periodo: 'June to October',
            meses: ['Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
            estrella: 'Marlin and dorado',
            descripcion: 'Warm water brings the big ones: the busiest season for anyone chasing a fight worth telling stories about.',
            otras: '',
            foto: '/photos/cana-doblada-dorado.webp',
            fuerte: true,
          },
          {
            periodo: 'November to December',
            meses: ['Nov', 'Dec'],
            estrella: 'Sierra',
            descripcion: 'The end of the year brings steady fishing and good weather for early starts, with sierra as the star.',
            otras: 'Triggerfish (cochito)',
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
          a: 'You can pick your preferred departure time between 5:00 and 7:00 am when booking. The tour lasts 6 to 7 hours to take full advantage of the best morning fishing conditions.',
        },
        {
          q: 'Where do we meet?',
          a: 'We meet at Marina La Costa (Rangel & Navarro, La Paz, BCS), right by Restaurant Marina La Costa. Once booked, we\'ll send you exact location details. If you prefer, you can also book a round-trip transfer to the activity with our fishing and transfer package.',
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
          a: 'Yes, Mexican regulations (CONAPESCA) require each angler on board to hold an individual sportfishing permit. You can add the licence process to your trip and we will gladly handle it for you.',
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
        video: '/videos/ventana-hero.webm',
        imagen: '/photos/ventana-poster.webp',
        posicionImagenMovil: '68% 50%',
        imagenCortina: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
        palabras: ['Pesca', 'Orcas', 'Ballenas', 'Snorkel', 'Mar', 'Aventura'],
        subtitulo:
          'Explora la pesca con mosca, el avistamiento de ballenas y orcas y los paquetes con hospedaje de La Ventana Travel.',
        facts: [],
      },
      dia: {
        titulo: 'Tu día en La Ventana',
        etiqueta: 'Tu día en La Ventana, momento por momento',
        momentos: [
          { titulo: '7:00 am', texto: 'Salimos todos los días entre 7:00 y 8:00 am, de La Ventana o de Bahía de los Sueños.', foto: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp' },
          { titulo: 'Snorkel', texto: 'Te damos el equipo para snorkelear y vamos a un arrecife a nadar entre los peces.', foto: '/catalogo/la-ventana-travel-paquete-7-noches.webp' },
          { titulo: 'En el mar', texto: 'Buscamos ballenas y orcas e intentamos nadar con ellos, según lo que haya en la temporada. Llevamos algo de comer, aguas y refrescos. En total, de 5 a 6 horas.', foto: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp' },
        ],
      },
      galeria: [
        {
          src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
          alt: 'Dos orcas nadando bajo la superficie del mar',
          ancho: 2000,
          alto: 1510,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
          alt: 'Vista aérea del Hotel Casa Arrecife con el mar de La Ventana al fondo',
          ancho: 2000,
          alto: 1118,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-paquete-5-noches.webp',
          alt: 'Una persona nadando entre un enorme cardumen de rayas',
          ancho: 2000,
          alto: 1334,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-hospedaje-fogata.webp',
          alt: 'La fogata azul del patio del Hotel Casa Arrecife al atardecer',
          ancho: 1856,
          alto: 2304,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-hospedaje-cocina.webp',
          alt: 'La cocina compartida del Hotel Casa Arrecife',
          ancho: 2000,
          alto: 1494,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-pesca-con-mosca.webp',
          alt: 'Un joven peleando un pez con la caña doblada, en alta mar',
          ancho: 2000,
          alto: 1500,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-paquete-7-noches.webp',
          alt: 'Una persona haciendo snorkel entre peces rayados',
          ancho: 1600,
          alto: 1280,
          empresaSlug: 'la-ventana-travel',
        },
      ],
      faq: [
        {
          q: '¿Qué incluye el paquete de 5 o de 7 noches?',
          a: 'Hospedaje en el Hotel Casa Arrecife durante 5 o 7 noches, traslado redondo del aeropuerto y el avistamiento de ballenas y orcas todos los días de mar: del día 2 al 5 en el paquete de 5 noches y del día 2 al 7 en el de 7. El día 1 es de llegada.',
        },
        {
          q: '¿Cómo es el hospedaje?',
          a: 'El Hotel Casa Arrecife tiene seis estudios (suites), cada uno para 2 personas y con una cama king size. La entrada es de 14:00 a 15:00 y la salida de 11:00 a 12:00. Está a 1 km de la playa de La Ventana y a 2.2 km del centro.',
        },
        {
          q: '¿Puedo viajar con niños? ¿Se puede agregar una cama extra o una cuna?',
          a: 'Niños de cualquier edad son bienvenidos. Cada estudio es para 2 personas con una cama king size, y no se pueden agregar camas extra ni cunas: tenlo en cuenta al elegir cuántas habitaciones reservar.',
        },
        {
          q: '¿A qué hora sale el avistamiento de ballenas y orcas y cuánto dura?',
          a: 'Salimos todos los días entre las 7:00 y las 8:00 am, de La Ventana o de Bahía de los Sueños. La salida dura de 5 a 6 horas, e incluye algo de comer, aguas y refrescos, y el equipo para snorkelear.',
        },
        {
          q: '¿Cuántas personas caben y puedo ir en un grupo privado?',
          a: 'Las pangas llevan hasta 7 personas y las más grandes hasta 10. Puedes ir en lancha compartida, pagando por persona, o con un grupo privado de hasta 10 personas: para el grupo privado escríbenos por WhatsApp y te ayudamos a reservarlo.',
        },
        {
          q: '¿Cómo funciona la pesca con mosca?',
          a: 'Es un día de pesca con mosca (fly fishing) para 2 o 3 personas como máximo. El precio es por día y por grupo, no por persona; lo ves en su tarjeta.',
        },
        {
          q: '¿La licencia de pesca está incluida?',
          a: 'No. La licencia de pesca es un extra y se paga aparte.',
        },
        {
          q: '¿Puedo cambiar la fecha o cancelar si hay mal clima?',
          a: 'Puedes cambiar la fecha con al menos 48 horas de anticipación. Si el mal clima impide salir, hay reembolso completo.',
        },
      ],
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
        video: '/videos/ventana-hero.webm',
        imagen: '/photos/ventana-poster.webp',
        posicionImagenMovil: '68% 50%',
        imagenCortina: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
        palabras: ['Fishing', 'Orcas', 'Whales', 'Snorkel', 'Sea', 'Adventure'],
        subtitulo:
          'Explore fly fishing, whale and orca watching, and packages with lodging from La Ventana Travel.',
        facts: [],
      },
      dia: {
        titulo: 'Your day in La Ventana',
        etiqueta: 'Your day in La Ventana, moment by moment',
        momentos: [
          { titulo: '7:00 am', texto: 'We leave every day between 7:00 and 8:00 am, from La Ventana or Bahía de los Sueños.', foto: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp' },
          { titulo: 'Snorkel', texto: 'We give you the snorkeling gear and head to a reef to swim among the fish.', foto: '/catalogo/la-ventana-travel-paquete-7-noches.webp' },
          { titulo: 'At sea', texto: 'We look for whales and orcas and try to swim with them, depending on the season. We bring some food, water and soft drinks. In all, 5 to 6 hours.', foto: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp' },
        ],
      },
      galeria: [
        {
          src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
          alt: 'Two orcas swimming just below the sea surface',
          ancho: 2000,
          alto: 1510,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
          alt: 'Aerial view of Hotel Casa Arrecife with the La Ventana sea behind it',
          ancho: 2000,
          alto: 1118,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-paquete-5-noches.webp',
          alt: 'A person swimming among a huge school of rays',
          ancho: 2000,
          alto: 1334,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-hospedaje-fogata.webp',
          alt: 'The blue fire pit in the Hotel Casa Arrecife courtyard at dusk',
          ancho: 1856,
          alto: 2304,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-hospedaje-cocina.webp',
          alt: 'The shared kitchen at Hotel Casa Arrecife',
          ancho: 2000,
          alto: 1494,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-pesca-con-mosca.webp',
          alt: 'A young angler fighting a fish with a bent rod, out at sea',
          ancho: 2000,
          alto: 1500,
          empresaSlug: 'la-ventana-travel',
        },
        {
          src: '/catalogo/la-ventana-travel-paquete-7-noches.webp',
          alt: 'A person snorkeling among striped fish',
          ancho: 1600,
          alto: 1280,
          empresaSlug: 'la-ventana-travel',
        },
      ],
      faq: [
        {
          q: 'What does the 5-night or 7-night package include?',
          a: 'Lodging at Hotel Casa Arrecife for 5 or 7 nights, a round-trip airport transfer, and whale and orca watching on every sea day: days 2 to 5 on the 5-night package and days 2 to 7 on the 7-night one. Day 1 is your arrival day.',
        },
        {
          q: 'What is the lodging like?',
          a: 'Hotel Casa Arrecife has six studios (suites), each for 2 people with one king size bed. Check-in is from 2:00 to 3:00 pm and check-out from 11:00 am to 12:00 pm. It is 1 km from La Ventana beach and 2.2 km from the town center.',
        },
        {
          q: 'Can I travel with children? Can an extra bed or a crib be added?',
          a: 'Children of all ages are welcome. Each studio is for 2 people with one king size bed, and extra beds and cribs cannot be added: keep this in mind when you choose how many rooms to book.',
        },
        {
          q: 'What time does whale and orca watching leave, and how long does it last?',
          a: 'We leave every day between 7:00 and 8:00 am, from La Ventana or Bahía de los Sueños. The trip lasts 5 to 6 hours and includes some food, water and soft drinks, and snorkeling gear.',
        },
        {
          q: 'How many people fit, and can I go in a private group?',
          a: 'The boats carry up to 7 people and the larger ones up to 10. You can go on a shared boat, paying per person, or with a private group of up to 10 people: for a private group, message us on WhatsApp and we will help you book it.',
        },
        {
          q: 'How does fly fishing work?',
          a: 'It is a day of fly fishing for 2 or 3 people at most. The price is per day and per group, not per person; you can see it on its card.',
        },
        {
          q: 'Is the fishing license included?',
          a: 'No. The fishing license is an extra and is paid separately.',
        },
        {
          q: 'Can I change the date or cancel if the weather is bad?',
          a: 'You can change the date with at least 48 hours notice. If bad weather keeps us from going out, you get a full refund.',
        },
      ],
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

/** @public Lo usan las pruebas. */
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
