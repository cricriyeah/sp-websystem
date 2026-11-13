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
        horarioApertura: '06:00',
        horarioCierre: '07:00',
      },
      metaTitle: 'Tours de pesca deportiva en La Paz, BCS | Sal y Sol Sportfishing',
      metaDescription:
        'Pesca deportiva en La Paz con capitanes que crecieron en la bahía. Panga solo para tu grupo, hasta 5 personas, saliendo cada mañana de Marina La Costa.',
      hero: {
        video: null,
        imagen: '/photos/panga-rumbo-a-la-pesca.webp',
        alt: 'Panga de Sal y Sol a toda velocidad en el Mar de Cortés, con los pescadores a bordo',
        // La cortina del hub conserva su foto.
        imagenCortina: '/photos/cola-amarilla-acantilado.webp',
        // Los tres pescadores están entre 31 % y 48 % del ancho: con 36 % la ventana del móvil los abarca.
        posicionImagenMovil: '36% 50%',
        palabras: ['Pesca', 'Dorado', 'Marlín', 'Jurel', 'Mar', 'Aventura', 'Sal y Sol'],
        encabezado: 'Pesca deportiva en panga privada',
        subtitulo:
          'Somos capitanes de La Paz y crecimos en esta bahía. Cada mañana salimos de Marina La Costa con tu grupo solo a bordo, a buscar lo que esté picando en el Mar de Cortés.',
        facts: [
          { value: '6 a 7 horas', label: 'En el mar' },
          { value: '{desde} a {hasta}', label: 'Tú eliges la hora de salida' },
          { value: 'Hasta 5 personas', label: 'Solo tu grupo a bordo' },
          { value: '365 días al año', label: 'Salimos todos los días' },
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
          { titulo: '{hora}', texto: 'Tu capitán te espera en el muelle de Marina La Costa con la panga lista. La hora la eliges tú, entre {desde} y {hasta}.', foto: '/photos/yellowtail-pelicanos-bahia.webp' },
          { titulo: 'A bordo', texto: 'En la panga van solo tu grupo y tu capitán. Él decide hacia dónde ir según cómo amaneció el mar.', foto: '/photos/capitan-cabrilla-bahia.webp' },
          { titulo: 'Pesca', texto: 'De 6 a 7 horas en el Mar de Cortés, buscando lo que da la temporada: dorado, marlín, jurel o sierra.', foto: '/photos/cana-doblada-dorado.webp' },
          { titulo: 'Regresa', texto: 'Vuelves al muelle con la captura y las fotos, y con los pelícanos rondando la panga a ver si les toca algo.', foto: '/photos/grupo-cabrilla-costa.webp' },
        ],
      },
      pangas: {
        titulo: 'La flota de Sal y Sol',
        flota: { src: '/photos/flota-pangas-bahia.webp', alt: 'Las siete pangas de Sal y Sol formadas en el agua turquesa de la bahía', ancho: 1600, alto: 894 },
        frase: 'Pangas de La Paz, capitanes de La Paz.',
        nombres: ['Don Piry', 'Volador', 'Dream', 'Escoria del Mar', 'Esperanzas', 'Storm', 'Volador III'],
        y: 'y',
        texto: '{nombres}. En el muelle las conocen por su nombre, igual que a sus capitanes, todos de La Paz.',
        fotos: [
          { src: '/photos/panga-rumbo-a-la-pesca.webp', alt: 'La panga Storm, con toldo verde, navega a toda velocidad con tres pescadores a bordo', pie: 'Storm' },
          { src: '/photos/panga-acantilados-rojos.webp', alt: 'La panga Volador III cruza el agua clara frente a acantilados rojos', pie: 'Volador III' },
        ],
      },
      // Los nombres de la tripulación los confirmó el dueño el 2026-10-30.
      conocenos: {
        titulo: 'Gente de mar',
        desde: { texto: 'MÁS DE 3 GENERACIONES DESDE', anio: '1950' },
        apertura: 'En La Paz, el oficio del mar se aprende de niño, en el muelle, viendo a los mayores salir antes de que amanezca.',
        historia: [
          'Así lo aprendieron nuestros capitanes. Son un gremio de gente de La Paz, y en él se repiten los apellidos, porque aquí el oficio pasa de padres a hijos. Crecieron en barrios de pescadores como El Manglito, viendo salir los barcos donde trabajaban sus padres y sus hermanos, y cualquiera de ellos te puede contar esa historia.',
          'Llevan la vida entera en esta agua. Saben dónde se junta el pescado en cada temporada, a qué hora se calma el viento y por dónde volver con la hielera llena. Cada salida es su trabajo y el sustento de su casa, y también la oportunidad de enseñarle su bahía a alguien que viene de lejos.',
        ],
        // Nunca el retrato del jefe solo: la foto del relato es de la gente del gremio.
        foto: { src: '/photos/capitanes-con-marlines.webp', alt: 'Dos hombres de mar sostienen un marlín cada uno en la popa de la panga' },
        ilustracion: { src: '/ilustraciones/dorado.svg', ancho: 710, alto: 723 },
        tripulacion: {
          titulo: 'STAFF DE CAPITANES',
          capitanes: [
            { nombre: 'Rogelio', apodo: 'Jolly Roger', detalle: 'Camacho' },
            { nombre: 'Omar', detalle: 'Oboli' },
            { nombre: 'Alfredo', apodo: 'Fetuccini', detalle: 'Camacho' },
            { nombre: 'Joel', detalle: 'Martínez' },
            { nombre: 'Licho', detalle: 'Camacho' },
            { nombre: 'Julio' },
            { nombre: 'Chito' },
            { nombre: 'Raúl', detalle: 'Martínez' },
            { nombre: 'Dagoberto', detalle: 'Usón' },
          ],
          y: 'y',
          fotos: [
            // Fotos de capitanes del staff (dueño, 2026-11-04). `posicion`: el punto que no se recorta.
            { src: '/photos/capitan-rogelio.webp', alt: 'El capitán Rogelio sostiene un dorado en la popa de la panga, con la bahía al fondo', posicion: '75% 50%' },
            { src: '/photos/capitan-chito.webp', alt: 'El capitán Chito levanta un atún aleta amarilla sobre la pesca del día', posicion: '50% 30%' },
            { src: '/photos/capitan-omar.webp', alt: 'El capitán Omar sonríe junto a un pez vela recién subido a la panga', posicion: '60% 38%' },
            { src: '/photos/joel-dorado.webp', alt: 'El capitán Joel y un pescador levantan entre los dos un dorado enorme', posicion: '50% 30%' },
          ],
        },
        cierre: { boton: 'Reservar tu salida' },
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
          src: '/photos/clientes-tuna.webp',
          alt: 'Dos pescadores sonríen con un pez grande recién subido, sobre la hielera de la panga',
          ancho: 768,
          alto: 1024,
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
          // Era cana-doblada-dorado (vertical: el cuadro ancho le cortaba la cabeza al cliente). Dueño, 2026-11-07.
          src: '/photos/cliente-dorado.webp',
          alt: 'Un pescador sentado en la popa levanta un dorado enorme, con una isla de la bahía al fondo',
          ancho: 1600,
          alto: 1200,
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
        intro: 'En la bahía, el pez cambia con el agua. Los capitanes lo leen en el color del mar y en los pájaros. Aquí lo tienes mes por mes, para que elijas tu fecha según lo que quieres pescar.',
        etiquetaCalendario: 'Calendario de pesca mes por mes',
        etiquetaFuerte: 'Temporada fuerte',
        etiquetaOtras: 'También activas',
        filas: [
          {
            periodo: 'Enero a abril',
            meses: ['Ene', 'Feb', 'Mar', 'Abr'],
            estrella: 'Jurel',
            descripcion: 'Agua fresca y mar en calma. El jurel pelea largo y hay que sujetar bien la caña.',
            otras: 'Pargo, cabrilla',
            foto: '/photos/yellowtail-pelicanos-bahia.webp',
            fuerte: false,
          },
          {
            periodo: 'Junio a octubre',
            meses: ['Jun', 'Jul', 'Ago', 'Sep', 'Oct'],
            estrella: 'Marlin y dorado',
            descripcion: 'Se calienta el agua y llegan el marlín y el dorado, los que saltan. Es la temporada fuerte del año.',
            otras: '',
            foto: '/photos/cana-doblada-dorado.webp',
            fuerte: true,
          },
          {
            periodo: 'Noviembre a diciembre',
            meses: ['Nov', 'Dic'],
            estrella: 'Sierra',
            descripcion: 'La sierra cierra el año, con pesca pareja y mañanas frescas para salir temprano.',
            otras: 'Cochito',
            foto: '/photos/joel-rallado-cliente.webp',
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
          a: 'Hay dos tamaños de panga: una para hasta 3 personas y otra para hasta 5. En las dos va solo tu grupo, y los niños de cualquier edad pueden ir.',
        },
        {
          q: '¿A qué hora salimos y cuánto dura?',
          a: 'Tú eliges la hora al reservar, entre las {desde} y las {hasta}. El viaje dura de 6 a 7 horas.',
        },
        {
          q: '¿Dónde nos vemos?',
          a: 'El punto de encuentro es en Marina La Costa (Rangel y Navarro, La Paz, BCS), junto al Restaurant Marina La Costa. Al reservar te enviamos la ubicación exacta y referencias. Si lo prefieres, puedes reservar también un traslado redondo a la actividad con nuestro paquete de pesca y traslado.',
        },
        {
          q: '¿Cómo puedo pagar?',
          a: 'Puedes pagar el 100 % en línea con tarjeta, o apartar tu fecha con el 30 % en línea y pagar el resto en efectivo. Aceptamos pesos mexicanos (MXN) y dólares (USD).',
        },
        {
          q: '¿Qué pasa si hay mal clima?',
          a: 'Si la capitanía de puerto o tu capitán deciden que el mar no está para salir, eliges entre cambiar la fecha o recibir el reembolso completo.',
        },
        {
          q: '¿Puedo cambiar la fecha de mi reserva?',
          a: 'Sí, sin costo, si avisas con al menos 48 horas y hay lugar en la nueva fecha, dentro de los 12 meses siguientes. Con menos tiempo, o si no llegas, el pago no se devuelve. Los detalles están en «Cambios y cancelaciones», al pie de la página.',
        },
        {
          q: '¿Necesito licencia de pesca?',
          a: 'Sí. La CONAPESCA, que regula la pesca en México, pide una licencia por cada persona que pesca a bordo. Puedes agregarla al reservar y nosotros la tramitamos.',
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
        horarioApertura: '06:00',
        horarioCierre: '07:00',
      },
      metaTitle: 'Sportfishing Charters in La Paz, BCS | Sal y Sol Sportfishing',
      metaDescription:
        'Sportfishing in La Paz with captains who grew up on the bay. A private panga for your group of up to 5, leaving Marina La Costa every morning.',
      hero: {
        video: null,
        imagen: '/photos/panga-rumbo-a-la-pesca.webp',
        alt: 'A Sal y Sol panga at full speed on the Sea of Cortez, with the anglers on board',
        // La cortina del hub conserva su foto.
        imagenCortina: '/photos/cola-amarilla-acantilado.webp',
        // Los tres pescadores están entre 31 % y 48 % del ancho: con 36 % la ventana del móvil los abarca.
        posicionImagenMovil: '36% 50%',
        palabras: ['Fishing', 'Mahi', 'Marlin', 'Yellowtail', 'Sea', 'Adventure', 'Sal y Sol'],
        encabezado: 'Private panga sportfishing charters',
        subtitulo:
          'We are La Paz captains, and we grew up on this bay. Every morning we leave Marina La Costa with only your group on board, to go after whatever is biting in the Sea of Cortez.',
        facts: [
          { value: '6 to 7 hours', label: 'On the water' },
          { value: '{desde} to {hasta}', label: 'You pick the departure time' },
          { value: 'Up to 5 guests', label: 'Only your group on board' },
          { value: '365 days a year', label: 'We go out every day' },
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
          { titulo: '{hora}', texto: 'Your captain meets you on the dock at Marina La Costa with the panga ready. You pick the time, between {desde} and {hasta}.', foto: '/photos/yellowtail-pelicanos-bahia.webp' },
          { titulo: 'On board', texto: 'Only your group and your captain on the panga. He decides where to head based on how the sea looks that morning.', foto: '/photos/capitan-cabrilla-bahia.webp' },
          { titulo: 'Fishing', texto: 'Six to seven hours on the Sea of Cortez, after whatever the season brings: dorado, marlin, yellowtail or sierra.', foto: '/photos/cana-doblada-dorado.webp' },
          { titulo: 'Return', texto: 'Back at the dock with your catch and your photos, and pelicans circling the panga hoping for a share.', foto: '/photos/grupo-cabrilla-costa.webp' },
        ],
      },
      pangas: {
        titulo: 'The Sal y Sol fleet',
        flota: { src: '/photos/flota-pangas-bahia.webp', alt: 'The seven Sal y Sol pangas lined up on the turquoise water of the bay', ancho: 1600, alto: 894 },
        frase: 'La Paz pangas, La Paz captains.',
        nombres: ['Don Piry', 'Volador', 'Dream', 'Escoria del Mar', 'Esperanzas', 'Storm', 'Volador III'],
        y: 'and',
        texto: '{nombres}. Everyone on the dock knows them by name, the same way they know their captains, all from La Paz.',
        fotos: [
          { src: '/photos/panga-rumbo-a-la-pesca.webp', alt: 'The panga Storm, with its green canopy, speeds across the water with three anglers on board', pie: 'Storm' },
          { src: '/photos/panga-acantilados-rojos.webp', alt: 'The panga Volador III crosses clear water in front of red cliffs', pie: 'Volador III' },
        ],
      },
      // Los nombres de la tripulación los confirmó el dueño el 2026-10-30.
      conocenos: {
        titulo: 'Born to this bay',
        desde: { texto: 'OVER 3 GENERATIONS SINCE', anio: '1950' },
        apertura: 'In La Paz, you learn the sea as a kid, on the dock, watching the older fishermen head out before sunrise.',
        historia: [
          'That’s how our captains learned it. They are a guild of La Paz locals, and the same last names come up again and again, because here the trade passes from parents to children. They grew up in fishing neighborhoods like El Manglito, watching the boats their fathers and brothers worked on head out, and any of them can tell you that story.',
          'They have spent their whole lives on this water. They know where the fish gather each season, when the wind lays down, and which way to come home with a full cooler. Every trip is their work and how they support their families, and it is also a chance to show their bay to someone who came a long way to see it.',
        ],
        // Placeholder until the owner sends the guild photo (never a portrait of the boss alone).
        foto: { src: '/photos/capitanes-con-marlines.webp', alt: 'Two seamen each hold a marlin at the stern of the panga' },
        ilustracion: { src: '/ilustraciones/dorado.svg', ancho: 710, alto: 723 },
        tripulacion: {
          titulo: 'OUR CAPTAINS',
          capitanes: [
            { nombre: 'Rogelio', apodo: 'Jolly Roger', detalle: 'Camacho' },
            { nombre: 'Omar', detalle: 'Oboli' },
            { nombre: 'Alfredo', apodo: 'Fetuccini', detalle: 'Camacho' },
            { nombre: 'Joel', detalle: 'Martínez' },
            { nombre: 'Licho', detalle: 'Camacho' },
            { nombre: 'Julio' },
            { nombre: 'Chito' },
            { nombre: 'Raúl', detalle: 'Martínez' },
            { nombre: 'Dagoberto', detalle: 'Usón' },
          ],
          y: 'and',
          fotos: [
            { src: '/photos/capitan-rogelio.webp', alt: 'Captain Rogelio holds a dorado at the stern of the panga, with the bay behind him', posicion: '75% 50%' },
            { src: '/photos/capitan-chito.webp', alt: 'Captain Chito lifts a yellowfin tuna over the day’s catch', posicion: '50% 30%' },
            { src: '/photos/capitan-omar.webp', alt: 'Captain Omar smiles next to a sailfish just brought aboard the panga', posicion: '60% 38%' },
            { src: '/photos/joel-dorado.webp', alt: 'Captain Joel and an angler lift a huge dorado together', posicion: '50% 30%' },
          ],
        },
        cierre: { boton: 'Book your trip' },
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
          src: '/photos/clientes-tuna.webp',
          alt: 'Two anglers grin with a big fish just brought aboard, resting on the panga\'s cooler',
          ancho: 768,
          alto: 1024,
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
          src: '/photos/cliente-dorado.webp',
          alt: 'An angler sitting at the stern holds up a huge dorado, with an island in the bay behind him',
          ancho: 1600,
          alto: 1200,
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
        intro: 'On the bay, the fish change with the water. The captains read it in the color of the sea and in the birds. Here it is month by month, so you can pick your dates around the fish you want.',
        etiquetaCalendario: 'Month-by-month fishing calendar',
        etiquetaFuerte: 'Peak season',
        etiquetaOtras: 'Also active',
        filas: [
          {
            periodo: 'January to April',
            meses: ['Jan', 'Feb', 'Mar', 'Apr'],
            estrella: 'Yellowtail',
            descripcion: 'Cool water and calm seas. Yellowtail fight long, so hold the rod tight.',
            otras: 'Snapper, cabrilla',
            foto: '/photos/yellowtail-pelicanos-bahia.webp',
            fuerte: false,
          },
          {
            periodo: 'June to October',
            meses: ['Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
            estrella: 'Marlin and dorado',
            descripcion: 'The water warms up and marlin and dorado arrive, the fish that jump. This is the peak season of the year.',
            otras: '',
            foto: '/photos/cana-doblada-dorado.webp',
            fuerte: true,
          },
          {
            periodo: 'November to December',
            meses: ['Nov', 'Dec'],
            estrella: 'Sierra',
            descripcion: 'Sierra close out the year, with steady fishing and cool mornings for early starts.',
            otras: 'Triggerfish (cochito)',
            foto: '/photos/joel-rallado-cliente.webp',
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
          a: 'There are two panga sizes: one for up to 3 people and one for up to 5. Either way it carries only your group, and kids of any age can come.',
        },
        {
          q: 'What time do we leave and how long is the trip?',
          a: 'You pick the time when you book, between {desde} and {hasta}. The trip lasts 6 to 7 hours.',
        },
        {
          q: 'Where do we meet?',
          a: 'We meet at Marina La Costa (Rangel & Navarro, La Paz, BCS), right by Restaurant Marina La Costa. Once booked, we\'ll send you exact location details. If you prefer, you can also book a round-trip transfer to the activity with our fishing and transfer package.',
        },
        {
          q: 'How can I pay?',
          a: 'You can pay 100% online by card, or hold your date with 30% online and pay the rest in cash. We accept Mexican pesos (MXN) and US dollars (USD).',
        },
        {
          q: 'What happens if the weather is bad?',
          a: 'If the port authority or your captain decides the sea isn’t safe to go out, you choose: move your date or get a full refund.',
        },
        {
          q: 'Can I change my booking date?',
          a: 'Yes, at no cost, if you give at least 48 hours notice and there is room on the new date, within the next 12 months. With less notice, or if you don’t show up, the payment is not refunded. The details are under «Changes and cancellations», at the bottom of the page.',
        },
        {
          q: 'Do I need a fishing licence?',
          a: 'Yes. CONAPESCA, the agency that regulates fishing in Mexico, requires a licence for each person fishing on board. You can add it when you book and we take care of the paperwork.',
        },
      ],
    },
  },
  'la-ventana': {
    es: {
      slug: 'la-ventana',
      empresaProtagonistaSlug: 'la-ventana-travel',
      negocio: null,
      metaTitle: 'Seafari de orcas y pesca con mosca en La Ventana, BCS | Sun Baja Experience',
      metaDescription:
        'Seafari de orcas y fauna marina y pesca con mosca en La Ventana, BCS, con La Ventana Travel. Paquetes de 5 y 7 noches con hospedaje en el Hotel Casa Arrecife y traslado de aeropuerto.',
      hero: {
        video: '/videos/ventana-hero.webm',
        imagen: '/photos/ventana-poster.webp',
        alt: 'Ballena jorobada vista desde el aire, junto a la espuma de su salida a la superficie',
        posicionImagenMovil: '68% 50%',
        imagenCortina: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
        palabras: ['Orcas', 'Seafari', 'Pesca', 'Snorkel', 'Mar', 'Aventura'],
        encabezado: 'Seafari de orcas y pesca con mosca',
        subtitulo:
          'La Ventana es un pueblo de playa y mucho viento, frente a la isla Cerralvo. Con La Ventana Travel sales a buscar orcas y fauna marina o a pescar con mosca, y puedes quedarte unas noches en el Hotel Casa Arrecife.',
        facts: [],
      },
      dia: {
        titulo: 'Tu día en La Ventana',
        etiqueta: 'Tu día en La Ventana, momento por momento',
        momentos: [
          { titulo: '7:00 am', texto: 'Salimos todos los días entre 7:00 y 8:00 am, de La Ventana o de Bahía de los Sueños.', foto: '/catalogo/la-ventana-travel-paquete-5-noches.webp' },
          { titulo: 'Snorkel', texto: 'Te damos el equipo para snorkelear y vamos a un arrecife a nadar entre los peces.', foto: '/catalogo/la-ventana-travel-paquete-7-noches.webp' },
          { titulo: 'En el mar', texto: 'Buscamos orcas, que vienen todo el año, y lo que el mar traiga ese día: delfines, lobos marinos y, desde abril, ballenas jorobadas y mobulas. Llevamos algo de comer, aguas y refrescos. En total, de 5 a 6 horas.', foto: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp' },
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
          ancho: 2750,
          alto: 1536,
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
          ancho: 2400,
          alto: 1792,
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
          a: 'Hospedaje en el Hotel Casa Arrecife durante 5 o 7 noches, traslado redondo del aeropuerto y el seafari de orcas y fauna marina todos los días de mar: del día 2 al 5 en el paquete de 5 noches y del día 2 al 7 en el de 7. El día 1 es de llegada.',
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
          q: '¿A qué hora sale el seafari y cuánto dura?',
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
          a: 'La pesca con mosca la cambias sin costo hasta 48 horas antes; los paquetes con hotel, hasta 30 días antes de tu llegada. Si el mal clima impide salir, eliges otra fecha o te devolvemos todo; en un paquete, la salida perdida se repone otro día de tu estancia. Los detalles están en «Cambios y cancelaciones», al pie de la página.',
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
      metaTitle: 'Orca Seafari and Fly Fishing Charters in La Ventana, BCS | Sun Baja Experience',
      metaDescription:
        'Orca and marine life seafaris and fly fishing in La Ventana, BCS, with La Ventana Travel. 5- and 7-night packages with lodging at Hotel Casa Arrecife and airport transfers.',
      hero: {
        video: '/videos/ventana-hero.webm',
        imagen: '/photos/ventana-poster.webp',
        alt: 'Humpback whale seen from above, next to the foam where it surfaced',
        posicionImagenMovil: '68% 50%',
        imagenCortina: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
        palabras: ['Orcas', 'Seafari', 'Fishing', 'Snorkel', 'Sea', 'Adventure'],
        encabezado: 'Orca seafari and fly fishing charters',
        subtitulo:
          'La Ventana is a windy beach town facing Cerralvo Island. With La Ventana Travel you head out to look for orcas and marine life or to fly fish, and you can stay a few nights at Hotel Casa Arrecife.',
        facts: [],
      },
      dia: {
        titulo: 'Your day in La Ventana',
        etiqueta: 'Your day in La Ventana, moment by moment',
        momentos: [
          { titulo: '7:00 am', texto: 'We leave every day between 7:00 and 8:00 am, from La Ventana or Bahía de los Sueños.', foto: '/catalogo/la-ventana-travel-paquete-5-noches.webp' },
          { titulo: 'Snorkel', texto: 'We give you the snorkeling gear and head to a reef to swim among the fish.', foto: '/catalogo/la-ventana-travel-paquete-7-noches.webp' },
          { titulo: 'At sea', texto: 'We look for orcas, which visit all year round, and whatever the sea brings that day: dolphins, sea lions and, from April, humpback whales and mobula rays. We bring some food, water and soft drinks. In all, 5 to 6 hours.', foto: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp' },
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
          ancho: 2750,
          alto: 1536,
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
          ancho: 2400,
          alto: 1792,
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
          a: 'Lodging at Hotel Casa Arrecife for 5 or 7 nights, a round-trip airport transfer, and an orca and marine life seafari on every sea day: days 2 to 5 on the 5-night package and days 2 to 7 on the 7-night one. Day 1 is your arrival day.',
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
          q: 'What time does the seafari leave, and how long does it last?',
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
          a: 'You can change a fly fishing day at no cost up to 48 hours before, and a package with hotel up to 30 days before arrival. If bad weather keeps us from going out, you choose another date or a full refund; on a package, the lost outing is replaced on another day of your stay. The details are under «Changes and cancellations», at the bottom of the page.',
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
        'Safari marino, ballena jorobada y pesca deportiva en el Pacífico con Piratas Adventures, una familia de Puerto Chale, en Bahía Magdalena.',
      // Fotos reales de Piratas Adventures (dueño, 2026-11-10). Textos pasados por humanizer y por las reglas de taste.
      hero: {
        video: '/videos/puertochale-hero.mp4',
        imagen: '/photos/puerto-chale/panga-entre-islas.webp',
        posicionImagenMovil: '58% 50%',
        palabras: ['Ballenas', 'Safari', 'Pesca', 'Bahía'],
        subtitulo:
          'Puerto Chale es un pueblo de pescadores en Bahía Magdalena, a donde la ballena jorobada llega cada invierno a tener a sus crías. Piratas Adventures es una familia de aquí y te lleva al safari marino, a ver a las ballenas y a pescar en el Pacífico.',
        facts: [],
      },
      // «Tu día» como en La Paz y La Ventana (dueño, 2026-11-12). Sin horas: la familia aún no da los horarios de salida.
      dia: {
        titulo: 'Tu día en Puerto Chale',
        etiqueta: 'Tu día en Puerto Chale, momento por momento',
        momentos: [
          { titulo: 'La bahía', texto: 'Sales en la panga de la familia a Bahía Magdalena, del lado del Pacífico.', foto: '/photos/puerto-chale/sol-sobre-la-isla.webp' },
          { titulo: 'Ballena jorobada', texto: 'De enero a marzo la ballena jorobada está en la bahía con sus crías y se acerca a la panga.', foto: '/photos/puerto-chale/ballena-y-la-sierra.webp' },
          { titulo: 'Safari marino', texto: 'Ocho horas recorriendo el mar entre islas, con lobos marinos y peces. Refrescos, aguas y comida sencilla van a bordo.', foto: '/photos/puerto-chale/lobos-marinos-bajo-el-agua.webp' },
          { titulo: 'Pesca', texto: 'Ocho horas de pesca en el Pacífico. Casi todos traen su propio equipo, y la licencia se agrega a tu reserva.', foto: '/photos/puerto-chale/buzos-con-marlines.webp' },
          { titulo: 'De regreso', texto: 'Al final del día, la panga vuelve al pueblo.', foto: '/photos/puerto-chale/estela-rumbo-al-pueblo.webp' },
        ],
      },
      familia: {
        // Relato a pedido del dueño (2026-11-12): emocional, como «Gente de mar», solo con lo que la familia contó.
        desde: { cifra: '+5', texto: 'GENERACIONES DE PESCADORES EN BAHÍA MAGDALENA' },
        titulo: 'Gente de la bahía',
        apertura: 'En Puerto Chale, el mar es el trabajo de toda la vida, y se hereda.',
        historia: [
          'Puerto Chale es un pueblo de pescadores a la orilla de Bahía Magdalena, del lado del Pacífico. Aquí el oficio pasa de padres a hijos, y Piratas Adventures es una de esas familias: llevan más de cinco generaciones saliendo al mar.',
          'Hoy salen padre e hijo. Conocen la bahía como su casa: por dónde entra el pescado, dónde se arriman las ballenas y a qué hora conviene volver.',
          'Cada invierno ven llegar a la ballena jorobada a tener a sus crías en la bahía. Y cada temporada se la enseñan, desde su panga, a quien viene de lejos.',
        ],
        foto: { src: '/photos/puerto-chale/ballenas-junto-a-la-panga.webp', alt: 'Dos ballenas jorobadas nadan pegadas a la panga mientras una pasajera las toca', posicion: '50% 60%' },
        retrato: { src: '/photos/puerto-chale/cristian-panga-atardecer.webp', alt: 'Cristian saluda desde su panga al atardecer, con el sol cayendo detrás de la isla', posicion: '50% 45%' },
        fotos: [
          { src: '/photos/puerto-chale/pesca-submarina-en-la-panga.webp', alt: 'Buzos en neopreno suben su pesca a la panga' },
          { src: '/photos/puerto-chale/ballena-de-cerca.webp', alt: 'El lomo de una ballena jorobada, cubierto de percebes, junto a la panga' },
        ],
        quien: { titulo: 'QUIÉN TE LLEVA', nombre: 'Cristian Bladimir Arce Murillo', detalles: ['Más de 15 años en el mar', 'Sale con su padre'] },
        cierre: { boton: 'Reservar tu salida' },
      },
      galeria: [
        { src: '/photos/puerto-chale/ballena-de-cerca.webp', alt: 'El lomo de una ballena jorobada, cubierto de percebes, junto a la panga', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/jorobada-saltando.webp', alt: 'Una ballena jorobada salta fuera del agua', ancho: 2000, alto: 1324, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/lobos-marinos-bajo-el-agua.webp', alt: 'Dos lobos marinos nadan bajo el agua', ancho: 1126, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/pesca-submarina-en-la-panga.webp', alt: 'Buzos en neopreno suben su pesca a la panga', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/arrecife-con-peces.webp', alt: 'Peces sobre el arrecife, con el sol entrando por la superficie', ancho: 1500, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/ballenas-junto-a-la-panga.webp', alt: 'Dos ballenas jorobadas nadan pegadas a la panga mientras una pasajera las toca', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/cardumen.webp', alt: 'Un cardumen de peces de colores', ancho: 1150, alto: 1369, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/jorobada-bajo-el-agua.webp', alt: 'Una ballena jorobada nada bajo el agua con las aletas abiertas', ancho: 2000, alto: 1324, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/ballena-bajo-el-agua.webp', alt: 'Una ballena jorobada pasa bajo el agua, a un lado de la panga', ancho: 900, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/buzos-con-marlines.webp', alt: 'Cuatro buzos en la panga con dos marlines', ancho: 1500, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/lobos-marinos-en-la-superficie.webp', alt: 'Lobos marinos asoman en la superficie del mar', ancho: 1334, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/ballena-y-la-sierra.webp', alt: 'Una ballena jorobada nada junto a la panga, con la sierra al fondo', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
      ],
      temporadas: {
        titulo: 'Qué hay cada temporada',
        nav: 'Temporadas',
        intro: 'Cada salida tiene su época. Aquí está mes por mes, para que elijas tu fecha.',
        etiquetaCalendario: 'Calendario de Puerto Chale mes por mes',
        etiquetaFuerte: 'Temporada fuerte',
        etiquetaOtras: 'También',
        filas: [
          {
            periodo: 'Enero a marzo',
            meses: ['Ene', 'Feb', 'Mar'],
            estrella: 'Ballena jorobada',
            descripcion: 'La ballena jorobada llega a la bahía a tener a sus crías. Es la temporada del avistamiento, en recorridos de 2 horas.',
            otras: '',
            foto: '/photos/puerto-chale/jorobada-saltando.webp',
            fuerte: true,
          },
          {
            periodo: 'Octubre a diciembre',
            meses: ['Oct', 'Nov', 'Dic'],
            estrella: 'Safari marino',
            descripcion: 'Ocho horas recorriendo el mar, con el lonche y las bebidas a bordo.',
            otras: '',
            foto: '/photos/puerto-chale/cardumen.webp',
            fuerte: false,
          },
          {
            periodo: 'Todo el año',
            meses: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            estrella: 'Pesca deportiva',
            descripcion: 'Ocho horas de pesca en el Pacífico. Casi todos los que vienen traen su propio equipo.',
            otras: '',
            foto: '/photos/puerto-chale/costa-e-islas.webp',
            fuerte: false,
          },
        ],
      },
      faq: [
        {
          q: '¿Tengo que llevar mi equipo de pesca?',
          a: 'Casi todos los que vienen a pescar traen su equipo: cañas, curricanes y señuelos. Si no tienes, pregúntanos por WhatsApp antes de reservar.',
        },
        {
          q: '¿Incluye comida y bebidas?',
          a: 'Sí, sin costo: refrescos, agua natural, agua mineral y sueros, y a veces cervezas si las pides. La comida es sencilla, como sándwiches o burritos. Si prefieres, puedes llevar tus propias bebidas y alimentos.',
        },
        {
          q: '¿Cuántas personas caben?',
          a: 'En el safari marino el precio es para 6 personas y caben 2 más con un cargo por persona. En el avistamiento de ballena jorobada el precio cubre de 1 a 6 personas, y cada persona extra paga $600 MXN, hasta 8. La pesca es para hasta 4. Si son más, se puede sumar otra embarcación avisando con anticipación.',
        },
        {
          q: '¿Cuánto dura el avistamiento de ballena jorobada?',
          a: 'El recorrido que reservas aquí es de 2 horas. Si quieres más tiempo, hay recorridos de 3 y 4 horas: pídelos por WhatsApp.',
        },
        {
          q: '¿Pueden ir niños?',
          a: 'A ver la ballena jorobada, sí. En la pesca, los niños y jóvenes vienen con sus padres. En el safari marino, los menores de edad necesitan una carta responsiva firmada por su madre, padre o tutor.',
        },
        {
          q: '¿La licencia de pesca está incluida?',
          a: 'No. La CONAPESCA, que regula la pesca en México, pide una licencia por cada persona que pesca a bordo. Puedes agregarla al reservar.',
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
      slug: 'puerto-chale',
      empresaProtagonistaSlug: 'piratas-adventures',
      negocio: null,
      metaTitle: 'Experiences in Puerto Chale, BCS | Sun Baja Experience',
      metaDescription:
        'Marine safaris, humpback whales and sportfishing on the Pacific with Piratas Adventures, a Puerto Chale family on Magdalena Bay.',
      hero: {
        video: '/videos/puertochale-hero.mp4',
        imagen: '/photos/puerto-chale/panga-entre-islas.webp',
        posicionImagenMovil: '58% 50%',
        palabras: ['Whales', 'Safari', 'Fishing', 'Bay'],
        subtitulo:
          'Puerto Chale is a fishing village on Magdalena Bay, where humpback whales arrive every winter to give birth. Piratas Adventures is a local family that takes you on marine safaris, out to see the whales and fishing on the Pacific.',
        facts: [],
      },
      dia: {
        titulo: 'Your day in Puerto Chale',
        etiqueta: 'Your day in Puerto Chale, moment by moment',
        momentos: [
          { titulo: 'The bay', texto: 'You head out in the family panga onto Magdalena Bay, on the Pacific side.', foto: '/photos/puerto-chale/sol-sobre-la-isla.webp' },
          { titulo: 'Humpback whales', texto: 'From January to March the humpback whales are in the bay with their calves and come close to the panga.', foto: '/photos/puerto-chale/ballena-y-la-sierra.webp' },
          { titulo: 'Marine safari', texto: 'Eight hours at sea among the islands, with sea lions and fish. Sodas, water and simple food are on board.', foto: '/photos/puerto-chale/lobos-marinos-bajo-el-agua.webp' },
          { titulo: 'Fishing', texto: 'Eight hours of fishing on the Pacific. Almost everyone brings their own gear, and the license is added to your booking.', foto: '/photos/puerto-chale/buzos-con-marlines.webp' },
          { titulo: 'Heading back', texto: 'At the end of the day, the panga heads back to the village.', foto: '/photos/puerto-chale/estela-rumbo-al-pueblo.webp' },
        ],
      },
      familia: {
        desde: { cifra: '5+', texto: 'GENERATIONS OF FISHERMEN ON MAGDALENA BAY' },
        titulo: 'People of the bay',
        apertura: 'In Puerto Chale, the sea is a lifetime of work, and it is handed down.',
        historia: [
          'Puerto Chale is a fishing village on the shore of Magdalena Bay, on the Pacific side. Here the trade passes from parents to children, and Piratas Adventures is one of those families: they have been going out to sea for more than five generations.',
          'Today a father and his son go out. They know the bay like their own home: where the fish come in, where the whales come close and what time it is best to head back.',
          'Every winter they watch the humpback whales arrive to give birth in the bay. And every season they show them, from their panga, to people who come from far away.',
        ],
        foto: { src: '/photos/puerto-chale/ballenas-junto-a-la-panga.webp', alt: 'Two humpback whales swim right beside the panga while a passenger reaches out to touch them', posicion: '50% 60%' },
        retrato: { src: '/photos/puerto-chale/cristian-panga-atardecer.webp', alt: 'Cristian waves from his panga at sunset, with the sun going down behind the island', posicion: '50% 45%' },
        fotos: [
          { src: '/photos/puerto-chale/pesca-submarina-en-la-panga.webp', alt: 'Divers in wetsuits bring their catch aboard the panga' },
          { src: '/photos/puerto-chale/ballena-de-cerca.webp', alt: 'The barnacled back of a humpback whale beside the panga' },
        ],
        quien: { titulo: 'WHO TAKES YOU OUT', nombre: 'Cristian Bladimir Arce Murillo', detalles: ['More than 15 years at sea', 'Goes out with his father'] },
        cierre: { boton: 'Book your trip' },
      },
      galeria: [
        { src: '/photos/puerto-chale/ballena-de-cerca.webp', alt: 'The barnacle-covered back of a humpback whale beside the panga', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/jorobada-saltando.webp', alt: 'A humpback whale breaches out of the water', ancho: 2000, alto: 1324, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/lobos-marinos-bajo-el-agua.webp', alt: 'Two sea lions swim underwater', ancho: 1126, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/pesca-submarina-en-la-panga.webp', alt: 'Divers in wetsuits bring their catch aboard the panga', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/arrecife-con-peces.webp', alt: 'Fish over the reef, with sunlight coming through the surface', ancho: 1500, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/ballenas-junto-a-la-panga.webp', alt: 'Two humpback whales swim right beside the panga while a passenger reaches out to touch them', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/cardumen.webp', alt: 'A school of colorful fish', ancho: 1150, alto: 1369, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/jorobada-bajo-el-agua.webp', alt: 'A humpback whale swims underwater with its fins spread', ancho: 2000, alto: 1324, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/ballena-bajo-el-agua.webp', alt: 'A humpback whale passes under the water beside the panga', ancho: 900, alto: 1600, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/buzos-con-marlines.webp', alt: 'Four divers in the panga with two marlin', ancho: 1500, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/lobos-marinos-en-la-superficie.webp', alt: 'Sea lions pop up at the surface', ancho: 1334, alto: 2000, empresaSlug: 'piratas-adventures' },
        { src: '/photos/puerto-chale/ballena-y-la-sierra.webp', alt: 'A humpback whale swims beside the panga, with the mountains behind', ancho: 1200, alto: 1600, empresaSlug: 'piratas-adventures' },
      ],
      temporadas: {
        titulo: 'What’s on each season',
        nav: 'Seasons',
        intro: 'Each trip has its time of year. Here it is month by month, so you can pick your dates.',
        etiquetaCalendario: 'Puerto Chale month-by-month calendar',
        etiquetaFuerte: 'Peak season',
        etiquetaOtras: 'Also',
        filas: [
          {
            periodo: 'January to March',
            meses: ['Jan', 'Feb', 'Mar'],
            estrella: 'Humpback whales',
            descripcion: 'The humpback whales come into the bay to give birth. This is whale-watching season, in 2-hour trips.',
            otras: '',
            foto: '/photos/puerto-chale/jorobada-saltando.webp',
            fuerte: true,
          },
          {
            periodo: 'October to December',
            meses: ['Oct', 'Nov', 'Dec'],
            estrella: 'Marine safari',
            descripcion: 'Eight hours out at sea, with lunch and drinks on board.',
            otras: '',
            foto: '/photos/puerto-chale/cardumen.webp',
            fuerte: false,
          },
          {
            periodo: 'All year',
            meses: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            estrella: 'Sportfishing',
            descripcion: 'Eight hours of fishing on the Pacific. Most people who come bring their own gear.',
            otras: '',
            foto: '/photos/puerto-chale/costa-e-islas.webp',
            fuerte: false,
          },
        ],
      },
      faq: [
        {
          q: 'Do I need to bring my own fishing gear?',
          a: 'Most people who come to fish bring their own gear: rods, trolling lures and baits. If you don’t have any, ask us on WhatsApp before you book.',
        },
        {
          q: 'Are food and drinks included?',
          a: 'Yes, at no cost: sodas, water, mineral water and electrolyte drinks, and sometimes beer if you ask. The food is simple, like sandwiches or burritos. If you prefer, you can bring your own drinks and food.',
        },
        {
          q: 'How many people fit?',
          a: 'The marine safari is priced for 6 people, with room for 2 more at a per-person charge. Humpback whale watching covers 1 to 6 people, and each extra person pays $600 MXN, up to 8. Fishing is for up to 4. For a bigger group, another boat can be added with some notice.',
        },
        {
          q: 'How long is the humpback whale trip?',
          a: 'The trip you book here is 2 hours. If you want more time, there are 3- and 4-hour trips: ask for them on WhatsApp.',
        },
        {
          q: 'Can children come?',
          a: 'To see the humpback whales, yes. On fishing trips, children and teens come with their parents. On the marine safari, minors need a release letter signed by a parent or guardian.',
        },
        {
          q: 'Is the fishing license included?',
          a: 'No. CONAPESCA, which regulates fishing in Mexico, requires a license for each person fishing on board. You can add it when you book.',
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
