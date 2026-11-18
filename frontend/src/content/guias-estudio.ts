// Guías que salieron del estudio de competencia en Google (203 búsquedas, 2026-11-16): búsquedas con primera página
// débil o sin operador local. Pesca en Puerto Chale y Bahía Magdalena, pesca en La Ventana, pez gallo con mosca,
// mobulas y safari marino, y una por especie de La Paz (dorado, marlín, jurel).
//
// Mismas reglas que `guias.ts`, que las junta en `GUIAS`:
// - Lo que ofrece cada empresa repite `sedes-cuerpo.ts`, `faq-servicios.ts` y `detalle-extra.ts`.
// - Lo que la empresa no ha confirmado (qué se pesca en Puerto Chale y en La Ventana, y en qué meses) va como dato de
//   la zona (`fuente: 'region'`) y con la invitación a preguntar por WhatsApp. El dueño lo cambia cuando lo confirme.
// - Sin cifras de precio escritas: la pregunta de precio lleva la marca de `lib/precio-en-texto.ts`.
// - Nunca se mencionan permisos ni dependencias de gobierno.
// - Las fotos son las del sitio, de relleno.

import type { DestinoGuia, Guia } from './guias';

const REVISADO = '2026-11-16';
const TODO_EL_ANIO = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
const JUNIO_A_OCTUBRE = [6, 7, 8, 9, 10];

const PAQUETES_VENTANA: DestinoGuia[] = [
  { tipo: 'paquete', sede: 'la-ventana', slug: 'paquete-5-noches', etiqueta: { es: 'Paquete de 5 noches', en: '5-night package' } },
  { tipo: 'paquete', sede: 'la-ventana', slug: 'paquete-7-noches', etiqueta: { es: 'Paquete de 7 noches', en: '7-night package' } },
];
const SEDE_LA_PAZ: DestinoGuia = { tipo: 'sede', slug: 'la-paz', etiqueta: { es: 'Pesca en La Paz', en: 'Fishing in La Paz' } };
const SEDE_VENTANA: DestinoGuia = { tipo: 'sede', slug: 'la-ventana', etiqueta: { es: 'Todo en La Ventana', en: 'Everything in La Ventana' } };
const SEDE_CHALE: DestinoGuia = { tipo: 'sede', slug: 'puerto-chale', etiqueta: { es: 'Todo en Puerto Chale', en: 'Everything in Puerto Chale' } };
const PESCA_LA_PAZ: DestinoGuia = { tipo: 'servicio', empresa: 'sal-y-sol', slug: 'pesca-deportiva', etiqueta: { es: 'Pesca deportiva en panga privada', en: 'Private panga fishing charter' } };
const PESCA_MOSCA: DestinoGuia = { tipo: 'servicio', empresa: 'la-ventana-travel', slug: 'pesca-con-mosca', etiqueta: { es: 'Pesca con mosca', en: 'Fly fishing' } };
const PESCA_CHALE: DestinoGuia = { tipo: 'servicio', empresa: 'piratas-adventures', slug: 'pesca-deportiva', etiqueta: { es: 'Pesca deportiva en Puerto Chale', en: 'Sportfishing from Puerto Chale' } };

// Fotos que se repiten entre estas guías.
const FOTO = {
  rumbo: { src: '/photos/panga-rumbo-a-la-pesca.webp', alt: { es: 'La panga Storm, con toldo verde, navega a toda velocidad con tres pescadores a bordo', en: 'The panga Storm, with its green canopy, speeds across the water with three anglers on board' } },
  acantilados: { src: '/photos/panga-acantilados-rojos.webp', alt: { es: 'La panga Volador III cruza el agua clara frente a acantilados rojos', en: 'The panga Volador III crosses clear water in front of red cliffs' } },
  flota: { src: '/photos/flota-pangas-bahia.webp', alt: { es: 'Las siete pangas de Sal y Sol formadas en el agua turquesa de la bahía', en: 'The seven Sal y Sol pangas lined up on the turquoise water of the bay' } },
  pelicanos: { src: '/photos/yellowtail-pelicanos-bahia.webp', alt: { es: 'De regreso a la bahía, con pelícanos alrededor', en: 'Heading back into the bay, pelicans alongside' } },
  toldo: { src: '/photos/dorado-bajo-toldo.webp', alt: { es: 'Dorado recién subido, a la sombra del toldo', en: 'Mahi just brought aboard, in the shade of the canopy' } },
  pangasPlaya: { src: '/sunbajaexperience/fotos/pangas-en-la-playa.webp', alt: { es: 'Pangas en la arena frente al mar', en: 'Pangas on the sand facing the sea' } },
  mosca: { src: '/catalogo/la-ventana-travel-pesca-con-mosca.webp', alt: { es: 'Un joven peleando un pez con la caña doblada, en alta mar', en: 'A young angler fighting a fish with a bent rod, out at sea' } },
  gallo: { src: '/photos/pez-gallo-a-bordo.webp', alt: { es: 'Dos pescadores sostienen un pez gallo enorme bajo el toldo de la panga', en: 'Two anglers hold up a huge roosterfish under the panga canopy' } },
  doradoColgado: { src: '/photos/cana-doblada-dorado.webp', alt: { es: 'Un pescador sonríe junto a un dorado verde y amarillo recién subido a la panga', en: 'An angler smiles beside a green-and-yellow dorado just brought aboard the panga' } },
  brazos: { src: '/sunbajaexperience/fotos/brazos-abiertos-al-mar.webp', alt: { es: 'Un hombre con los brazos abiertos frente al mar', en: 'A man with his arms spread wide facing the sea' } },
  salto: { src: '/sunbajaexperience/fotos/salto-al-mar.webp', alt: { es: 'Una persona salta al mar', en: 'A person jumps into the sea' } },
} as const;

// Lo que trae y lo que conviene llevar a una salida de Sal y Sol: lo mismo que dice la guía de pesca en panga.
const INCLUYE_LA_PAZ = {
  es: {
    titulo: '¿Qué incluye la salida?',
    parrafos: ['El precio trae lo necesario para que tú solo te ocupes de pescar. La licencia de pesca va aparte, solo para quien pesca.'],
    lista: ['Panga privada para tu grupo, con capitán local', 'Desayuno ligero y comida a bordo', 'Aperitivos y bebidas', 'Hielera con hielo para la captura'],
  },
  en: {
    titulo: 'What is included?',
    parrafos: ['The price covers what you need so that all you do is fish. The fishing license is separate, only for those who fish.'],
    lista: ['Private panga for your group, with a local captain', 'Light breakfast and lunch on board', 'Snacks and drinks', 'Ice chest with ice for the catch'],
  },
};
const LLEVAR_LA_PAZ = {
  es: {
    titulo: '¿Qué llevar?',
    parrafos: ['Poco, pero ayuda:'],
    lista: ['Una chamarra ligera o rompevientos para la brisa del amanecer', 'Pastillas para el mareo, si eres sensible al movimiento: se toman antes de zarpar', 'Una hielera para llevarte tus filetes al terminar', 'Bloqueador, gorra y lentes de sol'],
  },
  en: {
    titulo: 'What should I bring?',
    parrafos: ['Not much, but it helps:'],
    lista: ['A light jacket or windbreaker for the dawn breeze', 'Motion sickness tablets, if you are sensitive to movement: take them before leaving the dock', 'A cooler to take your fillets home', 'Sunscreen, a cap and sunglasses'],
  },
};
const PRECIO_LA_PAZ = {
  es: 'La panga privada con capitán cuesta {precio:sal-y-sol/pesca-deportiva} con IVA incluido, para {personas:sal-y-sol/pesca-deportiva} personas. Cada persona más paga {extra:sal-y-sol/pesca-deportiva}, hasta {maximo:sal-y-sol/pesca-deportiva}. El precio es el mismo todo el año, y puedes apartar con el {anticipo:sal-y-sol/pesca-deportiva}.',
  en: 'The private panga with a captain costs {precio:sal-y-sol/pesca-deportiva}, tax included, for {personas:sal-y-sol/pesca-deportiva} people. Each additional person pays {extra:sal-y-sol/pesca-deportiva}, up to {maximo:sal-y-sol/pesca-deportiva}. The price is the same all year, and you can hold your date with {anticipo:sal-y-sol/pesca-deportiva}.',
};
const CLIMA_LA_PAZ = {
  es: 'Eliges tú: cambias la fecha o recibes el reembolso completo. Aplica cuando la capitanía de puerto o tu capitán deciden que el mar no está para salir.',
  en: 'You choose: move your date or get a full refund. This applies when the port authority or your captain decides the sea is not fit to go out.',
};
const CUPO_LA_PAZ = {
  es: 'Hay pangas para hasta 3 y para hasta {maximo:sal-y-sol/pesca-deportiva} personas. En cualquiera va solo tu grupo.',
  en: 'There are pangas for up to 3 and for up to {maximo:sal-y-sol/pesca-deportiva} people. Either way it carries only your group.',
};
const INCLUYE_MOSCA = {
  es: ['Panga para tu grupo, hasta {maximo:la-ventana-travel/pesca-con-mosca} personas', 'Guía de pesca a bordo', 'Equipo de pesca: caña, carrete, moscas y líneas', 'Equipo de snorkel, por si quieres meterte al agua'],
  en: ['A panga for your group, up to {maximo:la-ventana-travel/pesca-con-mosca} people', 'A fishing guide on board', 'Fishing gear: rod, reel, flies and lines', 'Snorkeling gear, in case you want to get in the water'],
};

export const GUIAS_ESTUDIO: readonly Guia[] = [
  // Pesca en Puerto Chale y Bahía Magdalena ─────────────────────────────────────────────────────────────────────
  {
    id: 'pesca-puerto-chale',
    sede: 'puerto-chale',
    actualizado: REVISADO,
    foto: { src: '/photos/puerto-chale/buzos-con-marlines.webp', alt: { es: 'Cuatro buzos en la panga con dos marlines, en Puerto Chale', en: 'Four divers in the panga with two marlin, in Puerto Chale' } },
    destinos: [PESCA_CHALE, SEDE_CHALE],
    tema: 'mar',
    fotos: [
      { src: '/photos/puerto-chale/estela-rumbo-al-pueblo.webp', alt: { es: 'La estela de la panga, con el muelle de Puerto Chale al fondo', en: 'The wake of the panga, with the Puerto Chale dock behind' } },
      { src: '/photos/puerto-chale/pesca-submarina-en-la-panga.webp', alt: { es: 'Buzos en neopreno suben su pesca a la panga', en: 'Divers in wetsuits bring their catch aboard the panga' } },
      { src: '/photos/puerto-chale/cristian-panga-atardecer.webp', alt: { es: 'Cristian saluda desde su panga al atardecer, con el sol cayendo detrás de la isla', en: 'Cristian waves from his panga at sunset, with the sun going down behind the island' } },
      { src: '/photos/puerto-chale/cardumen.webp', alt: { es: 'Un cardumen de peces de colores', en: 'A school of colorful fish' } },
      { src: '/photos/puerto-chale/arrecife-con-peces.webp', alt: { es: 'Peces sobre el arrecife, con el sol entrando por la superficie', en: 'Fish over the reef, with sunlight coming through the surface' } },
    ],
    fotoFrase: { src: '/photos/puerto-chale/costa-e-islas.webp', alt: { es: 'El mar abierto con la isla al fondo y aves sobre el agua', en: 'Open sea with the island behind and birds over the water' } },
    textos: {
      es: {
        slug: 'pesca-en-puerto-chale-bahia-magdalena',
        titulo: 'Pesca en Puerto Chale: atún, marlín y pargo desde Bahía Almejas',
        metaTitulo: 'Pesca en Puerto Chale, Bahía Almejas: atún, marlín y pargo',
        metaDescripcion: 'Pesca deportiva en Puerto Chale, Bahía Almejas (Bahía Magdalena): atún, marlín y pargo en {duracion:piratas-adventures/pesca-deportiva} en el Pacífico con una familia de pescadores.',
        respuesta: 'En Puerto Chale, a la orilla de Bahía Almejas, sales a pescar atún, marlín y pargo con Piratas Adventures, una familia de pescadores del pueblo. Son {duracion:piratas-adventures/pesca-deportiva} en el Pacífico, en una panga para tu grupo de hasta {maximo:piratas-adventures/pesca-deportiva} personas, y se pesca todo el año.',
        frase: 'Sales con una familia que pesca aquí desde hace cinco generaciones.',
        datos: [
          { etiqueta: 'Duración', valor: '{duracion:piratas-adventures/pesca-deportiva}' },
          { etiqueta: 'Grupo', valor: 'Hasta {maximo:piratas-adventures/pesca-deportiva} personas' },
          { etiqueta: 'Temporada', valor: 'Todo el año' },
          { etiqueta: 'Desde La Paz', valor: 'De 1 h 40 min a 2 h' },
        ],
        calendario: {
          titulo: 'Qué se pesca en Puerto Chale, mes por mes',
          filas: [
            { nombre: 'Pesca deportiva', meses: TODO_EL_ANIO },
            { nombre: 'Marlín rayado', meses: [10, 11, 12], fuente: 'region' },
            { nombre: 'Atún', meses: [9, 10, 11], fuente: 'region' },
            { nombre: 'Pargo', meses: TODO_EL_ANIO, fuente: 'region' },
          ],
          nota: 'La primera fila es de Piratas Adventures: salen todo el año tras el atún, el marlín y el pargo. Los meses de cada especie vienen de los reportes de pesca de la zona y se mueven con el agua de cada año.',
        },
        secciones: [
          {
            titulo: '¿Cómo es un día de pesca en Puerto Chale?',
            parrafos: [
              'Sales del muelle del pueblo, en Bahía Almejas, en la panga de la familia. Son {duracion:piratas-adventures/pesca-deportiva} de pesca del lado del Pacífico, y la panga va solo con tu grupo, hasta {maximo:piratas-adventures/pesca-deportiva} personas.',
              'Quien te lleva conoce la bahía como su casa: por dónde entra el pescado y a qué hora conviene volver. Él decide el rumbo según cómo amaneció el mar.',
            ],
          },
          {
            titulo: '¿Qué se pesca en Puerto Chale?',
            parrafos: [
              'Con Piratas Adventures se pesca atún, marlín y pargo. Puerto Chale está en la orilla de Bahía Almejas, la parte sur de Bahía Magdalena, y de ahí la panga sale al Pacífico abierto.',
              'Los reportes de la zona hablan del marlín rayado mar afuera en otoño. Escríbenos por WhatsApp con tus fechas y te decimos qué está saliendo esa semana.',
            ],
          },
          {
            titulo: '¿Quién te lleva?',
            parrafos: [
              'Piratas Adventures es una familia de Puerto Chale con más de cinco generaciones de pescadores. Hoy salen padre e hijo: Cristian Bladimir Arce Murillo lleva más de 15 años en el mar.',
              'Es la misma familia que cada invierno lleva a ver a la ballena gris.',
            ],
          },
          {
            titulo: '¿Qué incluye y qué llevar?',
            parrafos: ['A bordo van refrescos, aguas, agua mineral y sueros sin costo, y comida sencilla si la quieres, como sándwiches o burritos. Esto lo traes tú:'],
            lista: [
              'Tu equipo de pesca: cañas, curricanes y señuelos. Si no tienes, escríbenos antes de reservar',
              'La licencia de pesca, que puedes agregar al reservar',
              'Bloqueador, gorra y lentes de sol',
              'Una chamarra ligera para la mañana',
            ],
          },
          {
            titulo: '¿Cómo llegar y cómo se reserva?',
            parrafos: [
              'Puerto Chale está a entre 1 hora 40 minutos y 2 horas de La Paz por carretera. La guía «Cómo llegar a Puerto Chale» trae la ruta completa.',
              'Reservas en línea con tarjeta. Puedes pagar todo o apartar tu fecha con el {anticipo:piratas-adventures/pesca-deportiva} y pagar el resto en efectivo. Si el mal clima impide salir, eliges otra fecha o la devolución completa.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuánto cuesta la pesca en Puerto Chale?', a: 'El día de pesca cuesta {precio:piratas-adventures/pesca-deportiva} con IVA incluido. El precio es por el grupo, hasta {maximo:piratas-adventures/pesca-deportiva} personas, y son {duracion:piratas-adventures/pesca-deportiva} en el Pacífico. La licencia de pesca se paga aparte.' },
          { q: '¿Qué se pesca en Puerto Chale?', a: 'Atún, marlín y pargo, en salidas de {duracion:piratas-adventures/pesca-deportiva} en el Pacífico con Piratas Adventures.' },
          { q: '¿Cuándo es la temporada de pesca en Bahía Magdalena?', a: 'Se pesca todo el año. De octubre a diciembre es cuando los reportes de la zona hablan del marlín rayado mar afuera.' },
          { q: '¿Dónde queda Bahía Almejas?', a: 'Es la parte sur de Bahía Magdalena, del lado del Pacífico, y Puerto Chale está en su orilla. De La Paz son de 1 hora 40 minutos a 2 horas por carretera.' },
          { q: '¿Tengo que llevar mi equipo de pesca?', a: 'Casi todos los que vienen traen su equipo: cañas, curricanes y señuelos. Si no tienes, escríbenos por WhatsApp antes de reservar.' },
          { q: '¿Necesito licencia de pesca?', a: 'Sí, una por cada persona que pesca a bordo. La agregas al reservar y nosotros la tramitamos.' },
          { q: '¿Cuántas personas pueden ir?', a: 'Hasta {maximo:piratas-adventures/pesca-deportiva}, y el precio es por el grupo.' },
        ],
        producto: { titulo: 'Reserva tu día de pesca', texto: '{duracion:piratas-adventures/pesca-deportiva} en el Pacífico con Piratas Adventures. El precio y las fechas libres están en su página.' },
      },
      en: {
        slug: 'puerto-chale-fishing-magdalena-bay',
        titulo: 'Puerto Chale fishing: tuna, marlin and snapper from Bahía Almejas',
        metaTitulo: 'Puerto Chale Fishing, Mag Bay: Tuna, Marlin & Snapper',
        metaDescripcion: 'Sportfishing from Puerto Chale on Bahía Almejas, Mag Bay: tuna, marlin and snapper, {duracion:piratas-adventures/pesca-deportiva} on the Pacific with a local fishing family.',
        respuesta: 'In Puerto Chale, on the shore of Bahía Almejas, you fish for tuna, marlin and snapper with Piratas Adventures, a fishing family from the village. It is {duracion:piratas-adventures/pesca-deportiva} on the Pacific, on a panga for your group of up to {maximo:piratas-adventures/pesca-deportiva} people, and they fish all year.',
        frase: 'You go out with a family that has fished here for five generations.',
        datos: [
          { etiqueta: 'Length', valor: '{duracion:piratas-adventures/pesca-deportiva}' },
          { etiqueta: 'Group', valor: 'Up to {maximo:piratas-adventures/pesca-deportiva} people' },
          { etiqueta: 'Season', valor: 'All year' },
          { etiqueta: 'From La Paz', valor: '1 h 40 min to 2 h' },
        ],
        calendario: {
          titulo: 'What you catch in Puerto Chale, month by month',
          filas: [
            { nombre: 'Sportfishing', meses: TODO_EL_ANIO },
            { nombre: 'Striped marlin', meses: [10, 11, 12], fuente: 'region' },
            { nombre: 'Tuna', meses: [9, 10, 11], fuente: 'region' },
            { nombre: 'Snapper', meses: TODO_EL_ANIO, fuente: 'region' },
          ],
          nota: 'The first row comes from Piratas Adventures: they fish all year for tuna, marlin and snapper. The months for each species come from the area’s fishing reports and shift with each year’s water.',
        },
        secciones: [
          {
            titulo: 'What is a fishing day in Puerto Chale like?',
            parrafos: [
              'You leave the village dock on Bahía Almejas in the family panga. It is {duracion:piratas-adventures/pesca-deportiva} of fishing on the Pacific side, and the panga carries only your group, up to {maximo:piratas-adventures/pesca-deportiva} people.',
              'The person taking you out knows the bay like home: where the fish come in and what time it is best to head back. He picks the heading by how the sea looks that morning.',
            ],
          },
          {
            titulo: 'What do you catch in Puerto Chale?',
            parrafos: [
              'With Piratas Adventures you fish for tuna, marlin and snapper. Puerto Chale sits on the shore of Bahía Almejas, the southern end of Magdalena Bay, and from there the panga runs out to the open Pacific.',
              'The area’s reports put striped marlin offshore in the fall. Message us on WhatsApp with your dates and we will tell you what is biting that week.',
            ],
          },
          {
            titulo: 'Who takes you out?',
            parrafos: [
              'Piratas Adventures is a Puerto Chale family with more than five generations of fishermen. Today a father and his son go out: Cristian Bladimir Arce Murillo has more than 15 years at sea.',
              'It is the same family that takes people to see the gray whales every winter.',
            ],
          },
          {
            titulo: 'What is included, and what should I bring?',
            parrafos: ['Sodas, water, mineral water and electrolyte drinks are on board at no cost, and simple food if you want it, such as sandwiches or burritos. This part is on you:'],
            lista: [
              'Your fishing gear: rods, trolling lures and baits. If you have none, message us before you book',
              'The fishing license, which you can add when you book',
              'Sunscreen, a cap and sunglasses',
              'A light jacket for the morning',
            ],
          },
          {
            titulo: 'How do I get there, and how do I book?',
            parrafos: [
              'Puerto Chale is a drive of 1 hour 40 minutes to 2 hours from La Paz. The guide “How to get to Puerto Chale” has the full route.',
              'You book online by card. You can pay in full or hold your date with {anticipo:piratas-adventures/pesca-deportiva} and pay the rest in cash. If bad weather keeps the boat in, you choose another date or a full refund.',
            ],
          },
        ],
        faq: [
          { q: 'How much does a fishing trip from Puerto Chale cost?', a: 'The fishing day costs {precio:piratas-adventures/pesca-deportiva}, tax included. The price is per group, up to {maximo:piratas-adventures/pesca-deportiva} people, for {duracion:piratas-adventures/pesca-deportiva} on the Pacific. The fishing license is paid separately.' },
          { q: 'What do you catch in Puerto Chale?', a: 'Tuna, marlin and snapper, on trips of {duracion:piratas-adventures/pesca-deportiva} on the Pacific with Piratas Adventures.' },
          { q: 'When is fishing season on Magdalena Bay?', a: 'You can fish all year. October to December is when the area’s reports talk about striped marlin offshore.' },
          { q: 'Where is Bahía Almejas?', a: 'It is the southern end of Magdalena Bay, on the Pacific side, and Puerto Chale sits on its shore. It is a drive of 1 hour 40 minutes to 2 hours from La Paz.' },
          { q: 'Do I need to bring my own fishing gear?', a: 'Almost everyone who comes brings their own gear: rods, trolling lures and baits. If you have none, message us on WhatsApp before you book.' },
          { q: 'Do I need a fishing license?', a: 'Yes, one for each person fishing on board. You add it when you book and we take care of it.' },
          { q: 'How many people can come?', a: 'Up to {maximo:piratas-adventures/pesca-deportiva}, and the price is per group.' },
        ],
        producto: { titulo: 'Book your fishing day', texto: '{duracion:piratas-adventures/pesca-deportiva} on the Pacific with Piratas Adventures. The price and open dates are on its page.' },
      },
    },
  },

  // Pesca en La Ventana ─────────────────────────────────────────────────────────────────────────────────────────
  {
    id: 'pesca-la-ventana',
    sede: 'la-ventana',
    actualizado: REVISADO,
    foto: FOTO.mosca,
    destinos: [PESCA_MOSCA, SEDE_VENTANA],
    tema: 'mar',
    fotos: [FOTO.pangasPlaya, FOTO.gallo, FOTO.doradoColgado, FOTO.salto, FOTO.acantilados],
    fotoFrase: FOTO.brazos,
    textos: {
      es: {
        slug: 'pesca-en-la-ventana-bcs',
        titulo: 'Pesca en La Ventana, BCS: qué se pesca y cómo reservar tu día',
        metaTitulo: 'Pesca deportiva en La Ventana, BCS: un día en panga con guía',
        metaDescripcion: 'Pesca en La Ventana, Baja California Sur: día completo en panga con guía y equipo de mosca incluido, para hasta {maximo:la-ventana-travel/pesca-con-mosca}. Qué se pesca frente a isla Cerralvo.',
        respuesta: 'En La Ventana pescas un día completo en panga, con guía de pesca a bordo y el equipo de mosca incluido. La panga es para tu grupo, hasta {maximo:la-ventana-travel/pesca-con-mosca} personas, frente a la isla Cerralvo, en el Mar de Cortés.',
        frase: 'Un día completo, tu panga y un guía que conoce estas aguas.',
        datos: [
          { etiqueta: 'Duración', valor: '{duracion:la-ventana-travel/pesca-con-mosca}' },
          { etiqueta: 'A bordo', valor: 'Hasta {maximo:la-ventana-travel/pesca-con-mosca} personas' },
          { etiqueta: 'Incluye', valor: 'Guía y equipo de mosca' },
          { etiqueta: 'Desde La Paz', valor: 'Unos 45 minutos' },
        ],
        calendario: {
          titulo: 'Qué se pesca en La Ventana, mes por mes',
          filas: [
            { nombre: 'Pez gallo', meses: [5, 6, 7], fuente: 'region' },
            { nombre: 'Dorado', meses: JUNIO_A_OCTUBRE, fuente: 'region' },
            { nombre: 'Jurel', meses: [1, 2, 3, 4], fuente: 'region' },
          ],
          nota: 'Son datos de la zona de La Paz y La Ventana, y se mueven con la temperatura del agua de cada año. Escríbenos con tus fechas y te decimos qué está saliendo.',
        },
        secciones: [
          {
            titulo: '¿Cómo es un día de pesca en La Ventana?',
            parrafos: [
              'Sales en panga con un guía de pesca. Es un día completo en el Mar de Cortés, entre la costa de La Ventana y la isla Cerralvo.',
              'La panga va solo con tu grupo, hasta {maximo:la-ventana-travel/pesca-con-mosca} personas. El precio es por el día y por el grupo, así que cuesta lo mismo para todo el grupo.',
            ],
          },
          {
            titulo: '¿Qué se pesca en La Ventana?',
            parrafos: [
              'El pez gallo es el pez por el que muchos pescadores vienen a esta costa: caza pegado a la playa y se le reconoce por la cresta. En el mismo mar se pescan dorado, jurel, pargo y bonito.',
              'Cada especie tiene sus meses, y cambian con la temperatura del agua. Escríbenos por WhatsApp con tus fechas y te decimos qué está saliendo.',
            ],
          },
          {
            titulo: '¿Qué incluye el día?',
            parrafos: ['Llegas sin equipo y pescas. Lo que sí conviene traer es tu lunch.'],
            lista: [...INCLUYE_MOSCA.es],
          },
          {
            titulo: '¿Sirve si nunca he pescado con mosca?',
            parrafos: ['Sí. El día es para principiantes y para expertos: el guía va a bordo y el equipo está incluido, así que puedes aprender ahí mismo.'],
          },
          {
            titulo: '¿Cómo llegar y dónde quedarte?',
            parrafos: [
              'La Ventana está a unos 45 minutos de La Paz por carretera y a unas 2 horas y media de Cabo San Lucas.',
              'Si quieres quedarte, los paquetes de 5 y 7 noches traen el Hotel Casa Arrecife y el traslado del aeropuerto. El día de pesca se reserva aparte, en la fecha que prefieras.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuánto cuesta un día de pesca en La Ventana?', a: 'El día completo cuesta {precio:la-ventana-travel/pesca-con-mosca} con IVA incluido, para un grupo de hasta {maximo:la-ventana-travel/pesca-con-mosca} personas. Reservas en línea con tarjeta y puedes apartar con el {anticipo:la-ventana-travel/pesca-con-mosca}.' },
          { q: '¿La licencia de pesca está incluida?', a: 'La licencia va aparte: es un extra que se paga por separado.' },
          { q: '¿Cuántas personas pueden ir en la panga?', a: 'Hasta {maximo:la-ventana-travel/pesca-con-mosca} por reserva, contando a quien pesca.' },
          { q: '¿Qué pasa si hay mal clima en La Ventana?', a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa.' },
        ],
        producto: { titulo: 'Reserva tu día de pesca', texto: 'Pesca con mosca con La Ventana Travel: día completo, guía y equipo. El precio y las fechas libres están en su página.' },
      },
      en: {
        slug: 'la-ventana-fishing-baja',
        titulo: 'La Ventana fishing, Baja: what you catch and how to book your day',
        metaTitulo: 'La Ventana Baja Fishing: Full-Day Panga Charter with a Guide',
        metaDescripcion: 'Fishing in La Ventana, Baja California Sur: a full day on a panga with a guide and fly gear included, for up to {maximo:la-ventana-travel/pesca-con-mosca}. What you catch off Cerralvo Island.',
        respuesta: 'In La Ventana you fish a full day on a panga, with a fishing guide on board and fly gear included. The panga is for your group, up to {maximo:la-ventana-travel/pesca-con-mosca} people, off Cerralvo Island in the Sea of Cortez.',
        frase: 'A full day, your own panga and a guide who knows these waters.',
        datos: [
          { etiqueta: 'Length', valor: '{duracion:la-ventana-travel/pesca-con-mosca}' },
          { etiqueta: 'On board', valor: 'Up to {maximo:la-ventana-travel/pesca-con-mosca} people' },
          { etiqueta: 'Included', valor: 'Guide and fly gear' },
          { etiqueta: 'From La Paz', valor: 'About 45 minutes' },
        ],
        calendario: {
          titulo: 'What you catch in La Ventana, month by month',
          filas: [
            { nombre: 'Roosterfish', meses: [5, 6, 7], fuente: 'region' },
            { nombre: 'Dorado (mahi mahi)', meses: JUNIO_A_OCTUBRE, fuente: 'region' },
            { nombre: 'Yellowtail', meses: [1, 2, 3, 4], fuente: 'region' },
          ],
          nota: 'This is data for the La Paz and La Ventana area, and it shifts with each year’s water temperature. Message us with your dates and we will tell you what is biting.',
        },
        secciones: [
          {
            titulo: 'What is a fishing day in La Ventana like?',
            parrafos: [
              'You head out on a panga with a fishing guide. It is a full day on the Sea of Cortez, between the La Ventana shore and Cerralvo Island.',
              'The panga carries only your group, up to {maximo:la-ventana-travel/pesca-con-mosca} people. The price is per day and per group, so it costs the same for the whole group.',
            ],
          },
          {
            titulo: 'What do you catch in La Ventana?',
            parrafos: [
              'Roosterfish are the fish many anglers come to this coast for: they hunt right along the beach and you know them by the comb. The same water holds dorado, yellowtail, snapper and bonito.',
              'Each species has its months, and they shift with the water temperature. Message us on WhatsApp with your dates and we will tell you what is biting.',
            ],
          },
          {
            titulo: 'What does the day include?',
            parrafos: ['You show up without gear and fish. What you should bring is your own lunch.'],
            lista: [...INCLUYE_MOSCA.en],
          },
          {
            titulo: 'Does it work if I have never fly fished?',
            parrafos: ['Yes. The day is for beginners and experts: the guide is on board and the gear is included, so you can learn right there.'],
          },
          {
            titulo: 'How do I get there, and where do I stay?',
            parrafos: [
              'La Ventana is about 45 minutes from La Paz by road and about 2 and a half hours from Cabo San Lucas.',
              'If you want to stay, the 5- and 7-night packages come with Hotel Casa Arrecife and airport transfers. The fishing day is booked separately, on the date you prefer.',
            ],
          },
        ],
        faq: [
          { q: 'How much does a fishing day in La Ventana cost?', a: 'The full day costs {precio:la-ventana-travel/pesca-con-mosca}, tax included, for a group of up to {maximo:la-ventana-travel/pesca-con-mosca} people. You book online by card and can hold your date with {anticipo:la-ventana-travel/pesca-con-mosca}.' },
          { q: 'Is the fishing license included?', a: 'The license is separate: it is an extra, paid on its own.' },
          { q: 'How many people can come on the panga?', a: 'Up to {maximo:la-ventana-travel/pesca-con-mosca} per booking, counting the angler.' },
          { q: 'What happens in bad weather in La Ventana?', a: 'If bad weather keeps the boat in, you choose: another date or a full refund.' },
        ],
        producto: { titulo: 'Book your fishing day', texto: 'Fly fishing with La Ventana Travel: a full day, guide and gear. The price and open dates are on its page.' },
      },
    },
  },

  // Pez gallo con mosca ─────────────────────────────────────────────────────────────────────────────────────────
  {
    id: 'pez-gallo-con-mosca',
    sede: 'la-ventana',
    actualizado: REVISADO,
    foto: FOTO.gallo,
    destinos: [PESCA_MOSCA, SEDE_VENTANA],
    tema: 'mar',
    fotos: [FOTO.pangasPlaya, FOTO.mosca, FOTO.acantilados, FOTO.doradoColgado],
    fotoFrase: FOTO.brazos,
    textos: {
      es: {
        slug: 'pez-gallo-con-mosca-la-ventana',
        titulo: 'Pez gallo con mosca en La Ventana: temporada, equipo y precio',
        metaTitulo: 'Pez gallo con mosca en La Ventana, BCS: temporada y precio',
        metaDescripcion: 'Pesca de pez gallo con mosca en La Ventana, Baja California Sur: día completo en panga con guía y equipo incluido. Cuándo ir y cuánto cuesta.',
        respuesta: 'El pez gallo caza pegado a la playa, y en La Ventana se le busca con mosca desde la panga. El día es completo, con guía de pesca a bordo y el equipo incluido. En la zona, sus meses van de mayo a julio.',
        frase: 'Lo ves venir por la cresta antes de lanzar.',
        datos: [
          { etiqueta: 'Meses en la zona', valor: 'De mayo a julio' },
          { etiqueta: 'Duración', valor: '{duracion:la-ventana-travel/pesca-con-mosca}' },
          { etiqueta: 'Equipo incluido', valor: 'Caña, carrete, moscas y líneas' },
          { etiqueta: 'Nivel', valor: 'Principiantes y expertos' },
        ],
        calendario: {
          titulo: 'Cuándo hay pez gallo en La Ventana',
          filas: [{ nombre: 'Pez gallo', meses: [5, 6, 7], fuente: 'region' }],
          nota: 'Dato de la zona: los meses se mueven con la temperatura del agua de cada año. Escríbenos y te decimos cómo viene la temporada.',
        },
        secciones: [
          {
            titulo: '¿Por qué el pez gallo?',
            parrafos: [
              'Es un pez de orilla. Persigue sardina y lisa a pocos metros de la playa, y cuando ataca levanta la cresta, esa aleta de espinas largas que le da el nombre.',
              'Vive solo en el Pacífico oriental, de Baja California a Perú. Por eso hay pescadores que cruzan el mundo para lanzarle una mosca en esta costa.',
            ],
          },
          {
            titulo: '¿Cómo se pesca con mosca?',
            parrafos: [
              'Se pesca a la vista. El guía busca al pez cerca de la orilla, acerca la panga y te dice cuándo y a dónde lanzar.',
              'El pez gallo pide lances largos y rápidos, así que ayuda llegar con algo de práctica. Si es tu primera vez con mosca, el guía te enseña a bordo.',
            ],
          },
          {
            titulo: '¿Qué incluye el día de pesca?',
            parrafos: ['El equipo va incluido, así que puedes viajar sin cañas. Lo que sí conviene traer es tu lunch.'],
            lista: [...INCLUYE_MOSCA.es],
          },
          {
            titulo: '¿Cuándo ir por pez gallo?',
            parrafos: [
              'En la zona de La Paz y La Ventana, los reportes de pesca ponen al pez gallo de mayo a julio, con el agua ya templada.',
              'El resto del año el día de pesca sigue saliendo, con lo que dé el mar: dorado, jurel, pargo o bonito.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuánto cuesta pescar pez gallo con mosca en La Ventana?', a: 'El día completo cuesta {precio:la-ventana-travel/pesca-con-mosca} con IVA incluido, para un grupo de hasta {maximo:la-ventana-travel/pesca-con-mosca} personas, con guía y equipo. Puedes apartar con el {anticipo:la-ventana-travel/pesca-con-mosca}.' },
          { q: '¿Necesito llevar mi equipo de mosca?', a: 'El equipo va incluido: caña, carrete, moscas y líneas. Si prefieres pescar con el tuyo, tráelo.' },
          { q: '¿Puedo ir si nunca he pescado con mosca?', a: 'Sí. El día es para principiantes y expertos, y el guía va a bordo.' },
          { q: '¿Cuántas personas pueden ir?', a: 'Hasta {maximo:la-ventana-travel/pesca-con-mosca} por reserva, contando a quien pesca.' },
          { q: '¿La licencia de pesca va incluida?', a: 'La licencia va aparte: es un extra que se paga por separado.' },
        ],
        producto: { titulo: 'Reserva tu día de mosca', texto: 'Día completo con La Ventana Travel, con guía y equipo incluido. El precio y las fechas libres están en su página.' },
      },
      en: {
        slug: 'roosterfish-fly-fishing-la-ventana',
        titulo: 'Roosterfish on the fly in La Ventana: season, gear and price',
        metaTitulo: 'Roosterfish Fly Fishing in La Ventana, Baja: Season & Price',
        metaDescripcion: 'Fly fishing for roosterfish in La Ventana, Baja California Sur: a full day on a panga with a guide and gear included. When to go and what it costs.',
        respuesta: 'Roosterfish hunt right along the beach, and in La Ventana you go after them on the fly from a panga. It is a full day, with a fishing guide on board and gear included. In this area their months run May through July.',
        frase: 'You see the comb coming before you cast.',
        datos: [
          { etiqueta: 'Months in the area', valor: 'May through July' },
          { etiqueta: 'Length', valor: '{duracion:la-ventana-travel/pesca-con-mosca}' },
          { etiqueta: 'Gear included', valor: 'Rod, reel, flies and lines' },
          { etiqueta: 'Level', valor: 'Beginners and experts' },
        ],
        calendario: {
          titulo: 'When roosterfish are in La Ventana',
          filas: [{ nombre: 'Roosterfish', meses: [5, 6, 7], fuente: 'region' }],
          nota: 'Area data: the months shift with each year’s water temperature. Message us and we will tell you how the season is shaping up.',
        },
        secciones: [
          {
            titulo: 'Why roosterfish?',
            parrafos: [
              'It is an inshore fish. It chases sardines and mullet a few yards off the beach, and when it attacks it raises the comb, the fin of long spines it is named for.',
              'It lives only in the eastern Pacific, from Baja California to Peru. That is why anglers cross the world to put a fly in front of one on this coast.',
            ],
          },
          {
            titulo: 'How do you fish for them on the fly?',
            parrafos: [
              'You sight fish. The guide looks for the fish near shore, brings the panga in and tells you when and where to cast.',
              'Roosterfish ask for long, fast casts, so it helps to arrive with some practice. If it is your first time with a fly rod, the guide teaches you on board.',
            ],
          },
          {
            titulo: 'What does the fishing day include?',
            parrafos: ['The gear is included, so you can travel without rods. What you should bring is your own lunch.'],
            lista: [...INCLUYE_MOSCA.en],
          },
          {
            titulo: 'When should I go for roosterfish?',
            parrafos: [
              'In the La Paz and La Ventana area, fishing reports put roosterfish from May through July, once the water has warmed.',
              'The rest of the year the fishing day still runs, with whatever the sea gives: dorado, yellowtail, snapper or bonito.',
            ],
          },
        ],
        faq: [
          { q: 'How much does roosterfish fly fishing in La Ventana cost?', a: 'The full day costs {precio:la-ventana-travel/pesca-con-mosca}, tax included, for a group of up to {maximo:la-ventana-travel/pesca-con-mosca} people, with a guide and gear. You can hold your date with {anticipo:la-ventana-travel/pesca-con-mosca}.' },
          { q: 'Do I need to bring my own fly gear?', a: 'The gear is included: rod, reel, flies and lines. If you would rather fish your own, bring it.' },
          { q: 'Can I come if I have never fly fished?', a: 'Yes. The day is for beginners and experts, and the guide is on board.' },
          { q: 'How many people can come?', a: 'Up to {maximo:la-ventana-travel/pesca-con-mosca} per booking, counting the angler.' },
          { q: 'Is the fishing license part of the price?', a: 'The license is separate: it is an extra, paid on its own.' },
        ],
        producto: { titulo: 'Book your fly fishing day', texto: 'A full day with La Ventana Travel, guide and gear included. The price and open dates are on its page.' },
      },
    },
  },

  // Mobulas y safari marino en La Ventana ───────────────────────────────────────────────────────────────────────
  {
    id: 'mobulas-la-ventana',
    sede: 'la-ventana',
    actualizado: REVISADO,
    foto: { src: '/catalogo/la-ventana-travel-paquete-5-noches.webp', alt: { es: 'Una persona nadando entre un enorme cardumen de rayas, frente a La Ventana', en: 'A person swimming among a huge school of rays off La Ventana' } },
    destinos: PAQUETES_VENTANA,
    tema: 'mar',
    fotos: [
      { src: '/catalogo/la-ventana-travel-paquete-7-noches.webp', alt: { es: 'Una persona haciendo snorkel entre peces rayados', en: 'A person snorkeling among striped fish' } },
      { src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp', alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' } },
      FOTO.pangasPlaya,
      FOTO.salto,
    ],
    fotoFrase: FOTO.brazos,
    textos: {
      es: {
        slug: 'mobulas-la-ventana-temporada',
        titulo: 'Mobulas en La Ventana: temporada y cómo verlas en el safari marino',
        metaTitulo: 'Mobulas en La Ventana, BCS: temporada y safari marino',
        metaDescripcion: 'Temporada de mobulas en La Ventana, Baja California Sur: de finales de abril a julio. Cómo es el safari marino para verlas saltar y cómo se reserva.',
        respuesta: 'Las mobulas llegan a La Ventana de finales de abril a julio. Se juntan en cardúmenes enormes frente a la isla Cerralvo y saltan fuera del agua. Las ves en el safari marino, la salida en lancha que va dentro de los paquetes de La Ventana.',
        frase: 'Saltan fuera del agua y caen de panza, una tras otra.',
        datos: [
          { etiqueta: 'Temporada', valor: 'Finales de abril a julio' },
          { etiqueta: 'Meses fuertes', valor: 'Mayo y junio' },
          { etiqueta: 'Salida', valor: 'entre las 7:00 y las 8:00 am' },
          { etiqueta: 'Cómo se reserva', valor: 'En paquetes de 5 y 7 noches' },
        ],
        calendario: {
          titulo: 'Cuándo hay mobulas en La Ventana',
          filas: [
            { nombre: 'Mobulas', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Orcas', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Delfines y lobos marinos', meses: TODO_EL_ANIO },
          ],
          nota: 'Son animales libres. Los meses marcados son los de más encuentros.',
        },
        secciones: [
          {
            titulo: '¿Qué son las mobulas?',
            parrafos: [
              'Son rayas, parientes chicas de la mantarraya gigante. Viajan en cardúmenes de miles y tienen una costumbre que se te queda grabada: saltan fuera del agua y caen de panza.',
              'Cada primavera se juntan en el sur del Mar de Cortés, y el canal entre La Ventana y la isla Cerralvo es uno de los lugares por donde pasan.',
            ],
          },
          {
            titulo: '¿Cuándo es la temporada de mobulas?',
            parrafos: [
              'De finales de abril a julio, con mayo y junio como los meses más fuertes. Son los mismos meses en que hay más encuentros con orcas, que llegan detrás de ellas a comer.',
            ],
          },
          {
            titulo: 'El safari marino: ¿cómo es la salida?',
            parrafos: [
              'Sales en lancha entre las 7:00 y las 8:00 am, de La Ventana o Bahía de los Sueños. Son 5 a 6 horas en el mar, con algo de comer, aguas, refrescos y el equipo de snorkel a bordo.',
              'A las mobulas las ves saltar desde la lancha. El día incluye una parada para snorkelear en un arrecife, y tu guía te avisa cuándo se puede entrar al agua.',
            ],
          },
          {
            titulo: '¿Qué más se ve en el safari marino?',
            parrafos: [
              'Orcas, delfines y lobos marinos. Desde abril también llegan las ballenas jorobadas, y hay días en que aparecen calderones, cachalotes o mantarrayas gigantes.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuándo es la temporada de mobulas en Baja California Sur?', a: 'En La Ventana, de finales de abril a julio. Mayo y junio son los meses más fuertes.' },
          { q: '¿Las mobulas se ven desde la lancha?', a: 'Sí. Saltan fuera del agua, así que se ven desde la lancha. El equipo de snorkel va a bordo y tu guía te avisa cuándo se puede entrar al agua.' },
          { q: '¿Puedo reservar solo un día de safari marino?', a: 'El safari marino se reserva dentro de los paquetes de 5 y 7 noches, con hotel, traslado del aeropuerto y de 4 a 6 salidas al mar. Con varias salidas tienes varias oportunidades de verlas.' },
          { q: '¿Qué pasa si el mar no deja salir?', a: 'Esa salida se repone otro día de tu estancia.' },
        ],
        producto: { titulo: 'Cómo ver las mobulas', texto: 'El safari marino va dentro de los paquetes de La Ventana Travel: hotel, traslado del aeropuerto y de 4 a 6 salidas al mar.' },
      },
      en: {
        slug: 'mobula-rays-la-ventana-season',
        titulo: 'Mobula rays in La Ventana: season and how to see them on an ocean safari',
        metaTitulo: 'Mobula Rays in La Ventana, Baja: Season & Ocean Safari',
        metaDescripcion: 'Mobula ray season in La Ventana, Baja California Sur: late April through July. What the ocean safari to watch them leap is like, and how to book it.',
        respuesta: 'Mobula rays arrive in La Ventana from late April through July. They gather in huge schools off Cerralvo Island and leap out of the water. You see them on the ocean safari, the boat trip that is part of the La Ventana packages.',
        frase: 'They leap out of the water and belly flop, one after another.',
        datos: [
          { etiqueta: 'Season', valor: 'Late April through July' },
          { etiqueta: 'Peak months', valor: 'May and June' },
          { etiqueta: 'Departure', valor: 'between 7:00 and 8:00 am' },
          { etiqueta: 'How to book', valor: 'In 5- and 7-night packages' },
        ],
        calendario: {
          titulo: 'When mobula rays are in La Ventana',
          filas: [
            { nombre: 'Mobula rays', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Orcas', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Dolphins and sea lions', meses: TODO_EL_ANIO },
          ],
          nota: 'These are wild animals. The marked months are the ones with the most encounters.',
        },
        secciones: [
          {
            titulo: 'What are mobula rays?',
            parrafos: [
              'They are rays, small relatives of the giant manta. They travel in schools of thousands and have a habit you do not forget: they leap out of the water and land flat on their bellies.',
              'Every spring they gather in the southern Sea of Cortez, and the channel between La Ventana and Cerralvo Island is one of the places they move through.',
            ],
          },
          {
            titulo: 'When is mobula ray season?',
            parrafos: [
              'Late April through July, with May and June as the strongest months. Those are also the months with the most orca encounters, since the orcas come in after the rays to feed.',
            ],
          },
          {
            titulo: 'The ocean safari: what is the trip like?',
            parrafos: [
              'You leave by boat between 7:00 and 8:00 am, from La Ventana or Bahía de los Sueños. You spend 5 to 6 hours at sea, with some food, water, soft drinks and snorkeling gear on board.',
              'You watch the mobulas leap from the boat. The day includes a snorkel stop at a reef, and your guide tells you when you can get in the water.',
            ],
          },
          {
            titulo: 'What else do you see on the ocean safari?',
            parrafos: [
              'Orcas, dolphins and sea lions. From April the humpback whales arrive too, and some days pilot whales, sperm whales or giant manta rays turn up.',
            ],
          },
        ],
        faq: [
          { q: 'When is mobula ray season in Baja California Sur?', a: 'In La Ventana, late April through July. May and June are the strongest months.' },
          { q: 'Can you see the mobula rays from the boat?', a: 'Yes. They leap out of the water, so you see them from the boat. Snorkeling gear is on board and your guide tells you when you can get in the water.' },
          { q: 'Can I book just one day of ocean safari?', a: 'The ocean safari is booked as part of the 5- and 7-night packages, with the hotel, airport transfers and 4 to 6 trips out to sea. Several trips give you several chances of seeing them.' },
          { q: 'What happens if the sea keeps the boat in?', a: 'That trip is made up on another day of your stay.' },
        ],
        producto: { titulo: 'How to see the mobula rays', texto: 'The ocean safari is part of La Ventana Travel’s packages: hotel, airport transfers and 4 to 6 trips out to sea.' },
      },
    },
  },

  // Dorado en La Paz ────────────────────────────────────────────────────────────────────────────────────────────
  {
    id: 'dorado-la-paz',
    sede: 'la-paz',
    actualizado: REVISADO,
    foto: FOTO.doradoColgado,
    destinos: [PESCA_LA_PAZ, SEDE_LA_PAZ],
    tema: 'mar',
    fotos: [
      { src: '/photos/cliente-dorado.webp', alt: { es: 'Un pescador levanta un dorado enorme en la popa de la panga, frente a La Paz', en: 'An angler holds up a huge dorado at the stern of the panga, off La Paz' } },
      { src: '/photos/pareja-dorados.webp', alt: { es: 'Dos amigos con su dorado', en: 'Two friends with their mahi' } },
      FOTO.rumbo,
      FOTO.toldo,
      { src: '/photos/joel-dorado.webp', alt: { es: 'El capitán Joel y un pescador levantan entre los dos un dorado enorme', en: 'Captain Joel and an angler lift a huge dorado together' } },
    ],
    fotoFrase: FOTO.acantilados,
    textos: {
      es: {
        slug: 'pesca-de-dorado-la-paz',
        titulo: 'Pesca de dorado en La Paz: temporada y cómo es el día',
        metaTitulo: 'Pesca de dorado en La Paz, BCS: temporada de junio a octubre',
        metaDescripcion: 'Temporada de dorado en La Paz, Baja California Sur: de junio a octubre. Cómo se pesca desde una panga privada con capitán local y cómo reservar.',
        respuesta: 'El dorado se pesca en La Paz de junio a octubre, la temporada fuerte del año. Sales en panga privada con un capitán local, durante {duracion:sal-y-sol/pesca-deportiva}, y a bordo va solo tu grupo.',
        frase: 'Verde y amarillo, y sale del agua saltando.',
        datos: [
          { etiqueta: 'Temporada', valor: 'Junio a octubre' },
          { etiqueta: 'Duración', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'A bordo', valor: 'Solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas' },
          { etiqueta: 'Sale de', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
        ],
        calendario: {
          titulo: 'Cuándo hay dorado en La Paz',
          filas: [
            { nombre: 'Dorado', meses: JUNIO_A_OCTUBRE, fuertes: JUNIO_A_OCTUBRE },
            { nombre: 'Marlín', meses: JUNIO_A_OCTUBRE },
            { nombre: 'Jurel', meses: [1, 2, 3, 4] },
          ],
          nota: 'Es el calendario de nuestros capitanes. Los meses se mueven un poco con la temperatura del agua de cada año.',
        },
        secciones: [
          {
            titulo: '¿Cómo es el dorado?',
            parrafos: [
              'Es de los peces más vistosos del mar: verde, amarillo y azul. Cuando pica, corre y salta fuera del agua, y por eso lo disfruta tanto quien pesca por primera vez.',
              'En inglés lo vas a oír como mahi mahi. Es el mismo pez.',
            ],
          },
          {
            titulo: '¿Cuándo es la temporada de dorado en La Paz?',
            parrafos: ['De junio a octubre, cuando el agua se calienta. Son los mismos meses del marlín, así que una misma salida puede dar para los dos.'],
          },
          {
            titulo: '¿Cómo se pesca dorado desde la panga?',
            parrafos: [
              'Tu capitán sale al amanecer de {salida:sal-y-sol/pesca-deportiva} y elige el rumbo según cómo amaneció el mar. El dorado anda cerca de la superficie y suele juntarse bajo lo que flota: sargazo, troncos, boyas.',
              'Pasas {duracion:sal-y-sol/pesca-deportiva} en el Mar de Cortés. El capitán te explica todo a bordo, así que puedes venir sin haber pescado nunca.',
            ],
          },
          INCLUYE_LA_PAZ.es,
          LLEVAR_LA_PAZ.es,
        ],
        faq: [
          { q: '¿Cuánto cuesta una salida de pesca de dorado en La Paz?', a: PRECIO_LA_PAZ.es },
          { q: '¿Cuál es el mejor mes para pescar dorado en La Paz?', a: 'De junio a octubre. Es la temporada fuerte del año y coincide con la del marlín.' },
          { q: '¿El dorado y el mahi mahi son el mismo pez?', a: 'Sí. Dorado es el nombre en español y mahi mahi, el que se usa en inglés.' },
          { q: '¿Pueden ir niños o gente que nunca ha pescado?', a: 'Sí. Pueden ir niños de cualquier edad, y el capitán te explica todo a bordo.' },
          { q: '¿Qué pasa si hay mal clima el día de mi salida?', a: CLIMA_LA_PAZ.es },
        ],
        producto: { titulo: 'Reserva tu salida de dorado', texto: 'Panga privada con un capitán de La Paz. El precio y las fechas libres están en su página.' },
      },
      en: {
        slug: 'la-paz-dorado-fishing',
        titulo: 'Dorado fishing in La Paz: season and what the day is like',
        metaTitulo: 'La Paz Dorado (Mahi Mahi) Fishing: Season June to October',
        metaDescripcion: 'Dorado (mahi mahi) season in La Paz, Baja California Sur: June to October. How you fish them from a private panga with a local captain, and how to book.',
        respuesta: 'Dorado (mahi mahi) are caught in La Paz from June to October, the peak season of the year. You go out on a private panga with a local captain for {duracion:sal-y-sol/pesca-deportiva}, with only your group on board.',
        frase: 'Green and gold, and it comes out of the water jumping.',
        datos: [
          { etiqueta: 'Season', valor: 'June to October' },
          { etiqueta: 'Length', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'On board', valor: 'Only your group, up to {maximo:sal-y-sol/pesca-deportiva} people' },
          { etiqueta: 'Leaves from', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
        ],
        calendario: {
          titulo: 'When dorado are in La Paz',
          filas: [
            { nombre: 'Dorado (mahi mahi)', meses: JUNIO_A_OCTUBRE, fuertes: JUNIO_A_OCTUBRE },
            { nombre: 'Marlin', meses: JUNIO_A_OCTUBRE },
            { nombre: 'Yellowtail', meses: [1, 2, 3, 4] },
          ],
          nota: 'This is our captains’ calendar. The months shift a little with each year’s water temperature.',
        },
        secciones: [
          {
            titulo: 'What is dorado like?',
            parrafos: [
              'It is one of the best-looking fish in the sea: green, gold and blue. When it bites it runs and jumps clear of the water, which is why first-time anglers enjoy it so much.',
              'You will also hear it called mahi mahi. It is the same fish.',
            ],
          },
          {
            titulo: 'When is dorado season in La Paz?',
            parrafos: ['June to October, when the water warms up. Those are the marlin months too, so one trip can give you a shot at both.'],
          },
          {
            titulo: 'How do you fish dorado from a panga?',
            parrafos: [
              'Your captain leaves {salida:sal-y-sol/pesca-deportiva} at dawn and picks the heading by how the sea looks that morning. Dorado stay near the surface and tend to gather under whatever floats: sargassum, logs, buoys.',
              'You spend {duracion:sal-y-sol/pesca-deportiva} on the Sea of Cortez. The captain walks you through everything on board, so you can come without ever having fished.',
            ],
          },
          INCLUYE_LA_PAZ.en,
          LLEVAR_LA_PAZ.en,
        ],
        faq: [
          { q: 'How much does a dorado fishing trip in La Paz cost?', a: PRECIO_LA_PAZ.en },
          { q: 'What is the best month for dorado fishing in La Paz?', a: 'June to October. It is the peak season of the year and overlaps with marlin.' },
          { q: 'Are dorado and mahi mahi the same fish?', a: 'Yes. Dorado is the Spanish name and mahi mahi the one used in English.' },
          { q: 'Can kids or first-timers come?', a: 'Yes. Kids of any age can come, and the captain walks you through everything on board.' },
          { q: 'What happens if the weather is bad on my trip day?', a: CLIMA_LA_PAZ.en },
        ],
        producto: { titulo: 'Book your dorado trip', texto: 'A private panga with a La Paz captain. The price and open dates are on its page.' },
      },
    },
  },

  // Marlín en La Paz ────────────────────────────────────────────────────────────────────────────────────────────
  {
    id: 'marlin-la-paz',
    sede: 'la-paz',
    actualizado: REVISADO,
    foto: { src: '/photos/capitanes-con-marlines.webp', alt: { es: 'Dos hombres de mar sostienen un marlín cada uno en la popa de la panga, en La Paz', en: 'Two seamen each hold a marlin at the stern of the panga, in La Paz' } },
    destinos: [PESCA_LA_PAZ, SEDE_LA_PAZ],
    tema: 'mar',
    fotos: [
      { src: '/photos/marlin-en-equipo.webp', alt: { es: 'Marlin capturado en equipo, listo para la foto y la liberación', en: 'Marlin landed as a team, ready for the photo and release' } },
      { src: '/photos/capitan-omar.webp', alt: { es: 'El capitán Omar sonríe junto a un pez vela recién subido a la panga', en: 'Captain Omar smiles next to a sailfish just brought aboard the panga' } },
      FOTO.rumbo,
      FOTO.flota,
      FOTO.pelicanos,
    ],
    fotoFrase: FOTO.acantilados,
    textos: {
      es: {
        slug: 'pesca-de-marlin-la-paz',
        titulo: 'Pesca de marlín en La Paz: temporada y cómo es la salida',
        metaTitulo: 'Pesca de marlín en La Paz, BCS: temporada y salida en panga',
        metaDescripcion: 'Temporada de marlín en La Paz, Baja California Sur: de junio a octubre. Cómo es buscarlo desde una panga privada con capitán local y cómo reservar.',
        respuesta: 'El marlín se pesca en La Paz de junio a octubre, con el agua caliente. Lo buscas desde una panga privada con un capitán local, en una salida de {duracion:sal-y-sol/pesca-deportiva} por el Mar de Cortés.',
        frase: 'Pica, salta y te toca aguantar.',
        datos: [
          { etiqueta: 'Temporada', valor: 'Junio a octubre' },
          { etiqueta: 'Duración', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'A bordo', valor: 'Solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas' },
          { etiqueta: 'Sale de', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
        ],
        calendario: {
          titulo: 'Cuándo hay marlín en La Paz',
          filas: [
            { nombre: 'Marlín', meses: JUNIO_A_OCTUBRE, fuertes: JUNIO_A_OCTUBRE },
            { nombre: 'Dorado', meses: JUNIO_A_OCTUBRE },
            { nombre: 'Pez vela', meses: [8, 9, 10], fuente: 'region' },
          ],
          nota: 'Las dos primeras filas son el calendario de nuestros capitanes. La del pez vela viene de los reportes de pesca de La Paz.',
        },
        secciones: [
          {
            titulo: '¿Qué marlín se pesca en La Paz?',
            parrafos: [
              'El más común en estas aguas es el marlín rayado, y con el agua más caliente también aparece el marlín azul. Son peces de pico: grandes, rápidos, y saltan cuando sienten el anzuelo.',
              'En la misma temporada sale el pez vela, su pariente de la aleta alta.',
            ],
          },
          {
            titulo: '¿Cuándo es la temporada de marlín en La Paz?',
            parrafos: ['De junio a octubre. Es la temporada fuerte de La Paz, la misma del dorado, y por la que más pescadores vienen.'],
          },
          {
            titulo: '¿Se pesca marlín desde una panga?',
            parrafos: [
              'Sí. La panga es la lancha de trabajo de los pescadores de La Paz, ligera y rápida, y los capitanes la conocen de memoria.',
              'Sales al amanecer de {salida:sal-y-sol/pesca-deportiva}. Tu capitán elige el rumbo según cómo amaneció el mar, y a bordo va solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas.',
            ],
          },
          INCLUYE_LA_PAZ.es,
          LLEVAR_LA_PAZ.es,
        ],
        faq: [
          { q: '¿Cuánto cuesta una salida de pesca de marlín en La Paz?', a: PRECIO_LA_PAZ.es },
          { q: '¿Cuál es el mejor mes para pescar marlín en La Paz?', a: 'De junio a octubre, con el agua caliente.' },
          { q: '¿Necesito experiencia para pescar marlín?', a: 'El capitán te explica todo a bordo. Ayuda venir con ganas de una pelea larga.' },
          { q: '¿Cuántas personas caben en la panga?', a: CUPO_LA_PAZ.es },
          { q: '¿Qué pasa si hay mal clima?', a: CLIMA_LA_PAZ.es },
        ],
        producto: { titulo: 'Reserva tu salida de marlín', texto: 'Panga privada con un capitán de La Paz, de junio a octubre. El precio y las fechas libres están en su página.' },
      },
      en: {
        slug: 'la-paz-marlin-fishing',
        titulo: 'Marlin fishing in La Paz: season and what the trip is like',
        metaTitulo: 'La Paz Marlin Fishing: Season & Private Panga Charters',
        metaDescripcion: 'Marlin season in La Paz, Baja California Sur: June to October. What it is like to go after them from a private panga with a local captain, and how to book.',
        respuesta: 'Marlin are caught in La Paz from June to October, when the water is warm. You go after them from a private panga with a local captain, on a 6- to 7-hour trip on the Sea of Cortez.',
        frase: 'It bites, it jumps, and then you hold on.',
        datos: [
          { etiqueta: 'Season', valor: 'June to October' },
          { etiqueta: 'Length', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'On board', valor: 'Only your group, up to {maximo:sal-y-sol/pesca-deportiva} people' },
          { etiqueta: 'Leaves from', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
        ],
        calendario: {
          titulo: 'When marlin are in La Paz',
          filas: [
            { nombre: 'Marlin', meses: JUNIO_A_OCTUBRE, fuertes: JUNIO_A_OCTUBRE },
            { nombre: 'Dorado (mahi mahi)', meses: JUNIO_A_OCTUBRE },
            { nombre: 'Sailfish', meses: [8, 9, 10], fuente: 'region' },
          ],
          nota: 'The first two rows are our captains’ calendar. The sailfish row comes from La Paz fishing reports.',
        },
        secciones: [
          {
            titulo: 'Which marlin do you catch in La Paz?',
            parrafos: [
              'The most common one in these waters is the striped marlin, and in the warmest water blue marlin show up too. They are billfish: big, fast, and they jump when they feel the hook.',
              'The same season brings sailfish, their relative with the tall fin.',
            ],
          },
          {
            titulo: 'When is marlin season in La Paz?',
            parrafos: ['June to October. It is peak season in La Paz, the same as dorado, and the one most anglers come for.'],
          },
          {
            titulo: 'Can you catch marlin from a panga?',
            parrafos: [
              'Yes. The panga is the working boat of La Paz fishermen, light and fast, and the captains know it by heart.',
              'You leave {salida:sal-y-sol/pesca-deportiva} at dawn. Your captain picks the heading by how the sea looks that morning, and only your group is on board, up to {maximo:sal-y-sol/pesca-deportiva} people.',
            ],
          },
          INCLUYE_LA_PAZ.en,
          LLEVAR_LA_PAZ.en,
        ],
        faq: [
          { q: 'How much does a marlin fishing trip in La Paz cost?', a: PRECIO_LA_PAZ.en },
          { q: 'What is the best month for marlin fishing in La Paz?', a: 'June to October, when the water is warm.' },
          { q: 'Do I need experience to fish for marlin?', a: 'The captain walks you through everything on board. It helps to come ready for a long fight.' },
          { q: 'How many people fit on the panga?', a: CUPO_LA_PAZ.en },
          { q: 'What happens in bad weather?', a: CLIMA_LA_PAZ.en },
        ],
        producto: { titulo: 'Book your marlin trip', texto: 'A private panga with a La Paz captain, June to October. The price and open dates are on its page.' },
      },
    },
  },

  // Jurel en La Paz ─────────────────────────────────────────────────────────────────────────────────────────────
  {
    id: 'jurel-la-paz',
    sede: 'la-paz',
    actualizado: REVISADO,
    foto: { src: '/photos/capitanes-con-jurel.webp', alt: { es: 'Un pescador levanta un jurel junto a su capitán, con la isla al fondo', en: 'An angler holds up a yellowtail next to his captain, with the island behind' } },
    destinos: [PESCA_LA_PAZ, SEDE_LA_PAZ],
    tema: 'mar',
    fotos: [
      { src: '/photos/jureles-en-la-bahia.webp', alt: { es: 'Un pescador muestra dos jureles en la panga, con La Paz al fondo', en: 'An angler shows two yellowtail on the panga, with La Paz behind' } },
      { src: '/catalogo/sal-y-sol-pesca-deportiva.webp', alt: { es: 'Jurel (cola amarilla) recién pescado frente a un acantilado', en: 'Freshly caught yellowtail by a sea cliff' } },
      FOTO.pelicanos,
      FOTO.toldo,
      FOTO.acantilados,
    ],
    fotoFrase: FOTO.flota,
    textos: {
      es: {
        slug: 'pesca-de-jurel-la-paz',
        titulo: 'Pesca de jurel en La Paz: temporada de invierno y cómo es el día',
        metaTitulo: 'Pesca de jurel (cola amarilla) en La Paz: enero a abril',
        metaDescripcion: 'Temporada de jurel en La Paz, Baja California Sur: de enero a abril. El pez del invierno, de pelea larga, desde una panga privada con capitán local.',
        respuesta: 'El jurel se pesca en La Paz de enero a abril, con el agua fresca y el mar en calma. Es el pez del invierno y pelea largo. Sales en panga privada con un capitán local, durante {duracion:sal-y-sol/pesca-deportiva}.',
        frase: 'Pelea largo y te va a pedir brazos.',
        datos: [
          { etiqueta: 'Temporada', valor: 'Enero a abril' },
          { etiqueta: 'Duración', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'A bordo', valor: 'Solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas' },
          { etiqueta: 'Sale de', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
        ],
        calendario: {
          titulo: 'Cuándo hay jurel en La Paz',
          filas: [
            { nombre: 'Jurel', meses: [1, 2, 3, 4] },
            { nombre: 'Sierra', meses: [11, 12] },
            { nombre: 'Marlín y dorado', meses: JUNIO_A_OCTUBRE, fuertes: JUNIO_A_OCTUBRE },
          ],
          nota: 'Es el calendario de nuestros capitanes. Los meses se mueven un poco con la temperatura del agua de cada año.',
        },
        secciones: [
          {
            titulo: '¿Cómo es el jurel?',
            parrafos: [
              'Aquí le decimos jurel; en inglés es yellowtail, por la cola amarilla. Es un pez fuerte, de cuerpo plateado, que tira hacia el fondo en cuanto siente el anzuelo.',
              'En las mismas salidas de invierno pican pargo y cabrilla.',
            ],
          },
          {
            titulo: '¿Cuándo es la temporada de jurel en La Paz?',
            parrafos: ['De enero a abril, con el agua fresca. Son meses de mar en calma y mañanas frías, así que conviene una chamarra para la salida.'],
          },
          {
            titulo: '¿Cómo es el día de pesca de jurel?',
            parrafos: [
              'Tu capitán te espera al amanecer en {salida:sal-y-sol/pesca-deportiva} con la panga lista y elige el rumbo según cómo amaneció el mar.',
              'Pasas {duracion:sal-y-sol/pesca-deportiva} en el Mar de Cortés. A bordo va solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas.',
            ],
          },
          INCLUYE_LA_PAZ.es,
          LLEVAR_LA_PAZ.es,
        ],
        faq: [
          { q: '¿Cuánto cuesta una salida de pesca de jurel en La Paz?', a: PRECIO_LA_PAZ.es },
          { q: '¿Se puede pescar en La Paz en invierno?', a: 'Sí. De enero a abril pica el jurel, con pargo y cabrilla. Salimos los 365 días del año.' },
          { q: '¿El jurel es el yellowtail?', a: 'Sí. En La Paz le decimos jurel, y en inglés se le conoce como yellowtail.' },
          { q: '¿Cuántas personas caben en la panga de pesca?', a: CUPO_LA_PAZ.es },
          { q: '¿Qué pasa si hay mal clima en invierno?', a: CLIMA_LA_PAZ.es },
        ],
        producto: { titulo: 'Reserva tu salida de jurel', texto: 'Panga privada con un capitán de La Paz, de enero a abril. El precio y las fechas libres están en su página.' },
      },
      en: {
        slug: 'la-paz-yellowtail-fishing',
        titulo: 'Yellowtail fishing in La Paz: the winter season and what the day is like',
        metaTitulo: 'La Paz Yellowtail Fishing: Winter Season, January to April',
        metaDescripcion: 'Yellowtail season in La Paz, Baja California Sur: January to April. The winter fish, with a long fight, from a private panga with a local captain.',
        respuesta: 'Yellowtail are caught in La Paz from January to April, when the water is cool and the sea is calm. It is the winter fish and it fights long. You go out on a private panga with a local captain for {duracion:sal-y-sol/pesca-deportiva}.',
        frase: 'It fights long and it will ask for your arms.',
        datos: [
          { etiqueta: 'Season', valor: 'January to April' },
          { etiqueta: 'Length', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'On board', valor: 'Only your group, up to {maximo:sal-y-sol/pesca-deportiva} people' },
          { etiqueta: 'Leaves from', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
        ],
        calendario: {
          titulo: 'When yellowtail are in La Paz',
          filas: [
            { nombre: 'Yellowtail', meses: [1, 2, 3, 4] },
            { nombre: 'Sierra', meses: [11, 12] },
            { nombre: 'Marlin and dorado', meses: JUNIO_A_OCTUBRE, fuertes: JUNIO_A_OCTUBRE },
          ],
          nota: 'This is our captains’ calendar. The months shift a little with each year’s water temperature.',
        },
        secciones: [
          {
            titulo: 'What is yellowtail like?',
            parrafos: [
              'Here we call it jurel; in English it is yellowtail, for the yellow tail. It is a strong, silver-bodied fish that pulls for the bottom the moment it feels the hook.',
              'The same winter trips bring snapper and cabrilla.',
            ],
          },
          {
            titulo: 'When is yellowtail season in La Paz?',
            parrafos: ['January to April, when the water is cool. Those are months of calm seas and cold mornings, so bring a jacket for the ride out.'],
          },
          {
            titulo: 'What is a yellowtail fishing day like?',
            parrafos: [
              'Your captain is waiting at dawn at {salida:sal-y-sol/pesca-deportiva} with the panga ready, and picks the heading by how the sea looks that morning.',
              'You spend {duracion:sal-y-sol/pesca-deportiva} on the Sea of Cortez. Only your group is on board, up to {maximo:sal-y-sol/pesca-deportiva} people.',
            ],
          },
          INCLUYE_LA_PAZ.en,
          LLEVAR_LA_PAZ.en,
        ],
        faq: [
          { q: 'How much does a yellowtail fishing trip in La Paz cost?', a: PRECIO_LA_PAZ.en },
          { q: 'Can you fish in La Paz in winter?', a: 'Yes. January to April is yellowtail, with snapper and cabrilla. We go out 365 days a year.' },
          { q: 'Is jurel the same as yellowtail?', a: 'Yes. In La Paz we call it jurel, and in English it is known as yellowtail.' },
          { q: 'How many people fit on the fishing panga?', a: CUPO_LA_PAZ.en },
          { q: 'What happens in bad weather in winter?', a: CLIMA_LA_PAZ.en },
        ],
        producto: { titulo: 'Book your yellowtail trip', texto: 'A private panga with a La Paz captain, January to April. The price and open dates are on its page.' },
      },
    },
  },
];
