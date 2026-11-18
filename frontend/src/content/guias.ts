// Guías del sitio: una pregunta por página (cuándo, dónde, cómo), contestada arriba y con el camino a lo que se reserva.
//
// De dónde sale cada dato (auditoría SEO, 2026-11-13):
// - Lo que ofrecen las empresas (horarios, duración, cupo, qué incluye, temporadas propias) es lo mismo que dicen
//   `sedes-cuerpo.ts` y `faq-servicios.ts`. Si cambia allá, se cambia aquí.
// - Lo general de la región (migración de la ballena gris, temporada de mobulas, viento, especies de pesca que el
//   calendario de la sede no trae, la ruta a Puerto Chale) sale de fuentes públicas y va dicho como rango, no como
//   promesa. Esas filas llevan `fuente: 'region'`.
// - Sin cifras de precio escritas: cambian en el backoffice. La pregunta «¿Cuánto cuesta…?» lleva una marca
//   (`{precio:<empresa>/<servicio>}`, `lib/precio-en-texto.ts`) y la página pone la cifra del catálogo.
// - Nunca se mencionan permisos ni dependencias de gobierno sobre el nado con orcas (decisión del dueño).
// - Las fotos de las secciones son las que ya hay en el sitio, puestas de relleno (se repiten entre guías): el dueño
//   las cambia después. La descripción de cada una es la misma que lleva en `sedes-cuerpo.ts`.

import { GUIAS_ESTUDIO } from './guias-estudio';

export type IdiomaGuia = 'es' | 'en';
type Texto = Record<IdiomaGuia, string>;

/** A dónde lleva la guía: lo que se reserva para vivir lo que explica. */
export type DestinoGuia =
  | { tipo: 'paquete'; sede: string; slug: string; etiqueta: Texto }
  | { tipo: 'servicio'; empresa: string; slug: string; etiqueta: Texto }
  | { tipo: 'sede'; slug: string; etiqueta: Texto };

export type TemaGuia = 'mar' | 'traslado' | 'estancia';
type FotoGuia = { src: string; alt: Texto };

export type FilaCalendario = {
  nombre: string;
  /** Meses en que se ve o se pesca, de 1 (enero) a 12 (diciembre). */
  meses: number[];
  /** Los meses fuertes, si los hay. */
  fuertes?: number[];
  /** `region`: el dato es de fuentes públicas de la zona, no de la empresa. */
  fuente?: 'region';
};

export type GuiaTexto = {
  slug: string;
  /** El `h1`: la pregunta o el tema, con las palabras que se buscan. */
  titulo: string;
  /** Título de la pestaña, completo: 62 caracteres como máximo. */
  metaTitulo: string;
  /** 155 caracteres como máximo. */
  metaDescripcion: string;
  /** La respuesta directa, en dos o tres frases: es lo primero que se lee. */
  respuesta: string;
  /** Una frase corta que se lee sola, en letra grande sobre una foto: lo que la guía deja en la cabeza. */
  frase: string;
  /** Hasta cuatro datos sueltos: etiqueta corta y valor. */
  datos: { etiqueta: string; valor: string }[];
  calendario?: { titulo: string; filas: FilaCalendario[]; nota: string };
  secciones: { titulo: string; parrafos: string[]; lista?: string[] }[];
  faq: { q: string; a: string }[];
  /** El bloque de lo que se reserva: título y una frase. */
  producto: { titulo: string; texto: string };
};

export type Guia = {
  id: string;
  /** La sede de la que habla; `null` si es de toda la región. */
  sede: 'la-paz' | 'la-ventana' | 'puerto-chale' | null;
  /** Fecha de la última revisión del texto (AAAA-MM-DD). */
  actualizado: string;
  /** La foto del arranque. */
  foto: FotoGuia;
  /**
   * De qué trata, con el significado de color del sitio: azul = mar, coral = traslados, verde = estancia. Solo pinta
   * acentos (las casillas del calendario, las palomitas, la marca de una tarjeta), nunca un fondo de sección.
   */
  tema: TemaGuia;
  /** La foto de cada sección, en el mismo orden que `secciones` (las dos versiones tienen las mismas). */
  fotos: FotoGuia[];
  /** La foto a sangre sobre la que va la `frase`. */
  fotoFrase: FotoGuia;
  destinos: DestinoGuia[];
  textos: Record<IdiomaGuia, GuiaTexto>;
};

const ACTUALIZADO = '2026-11-13';
// Las guías escritas o revisadas con el estudio de competencia en Google (203 búsquedas, 2026-11-16).
const REVISADO = '2026-11-16';
const TODO_EL_ANIO = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

const PAQUETES_VENTANA: DestinoGuia[] = [
  { tipo: 'paquete', sede: 'la-ventana', slug: 'paquete-5-noches', etiqueta: { es: 'Paquete de 5 noches', en: '5-night package' } },
  { tipo: 'paquete', sede: 'la-ventana', slug: 'paquete-7-noches', etiqueta: { es: 'Paquete de 7 noches', en: '7-night package' } },
];
const SEDE_LA_PAZ: DestinoGuia = { tipo: 'sede', slug: 'la-paz', etiqueta: { es: 'Pesca en La Paz', en: 'Fishing in La Paz' } };
const SEDE_VENTANA: DestinoGuia = { tipo: 'sede', slug: 'la-ventana', etiqueta: { es: 'Todo en La Ventana', en: 'Everything in La Ventana' } };
const SEDE_CHALE: DestinoGuia = { tipo: 'sede', slug: 'puerto-chale', etiqueta: { es: 'Todo en Puerto Chale', en: 'Everything in Puerto Chale' } };
const PESCA_LA_PAZ: DestinoGuia = { tipo: 'servicio', empresa: 'sal-y-sol', slug: 'pesca-deportiva', etiqueta: { es: 'Pesca deportiva en panga privada', en: 'Private panga fishing charter' } };
const BALLENAS_CHALE: DestinoGuia = { tipo: 'servicio', empresa: 'piratas-adventures', slug: 'avistamiento-ballenas', etiqueta: { es: 'Avistamiento de ballenas', en: 'Whale watching' } };

export const GUIAS: readonly Guia[] = [
  // 1. Nado con orcas en La Ventana ────────────────────────────────────────────────────────────────────────────
  {
    id: 'orcas-la-ventana',
    sede: 'la-ventana',
    actualizado: REVISADO,
    foto: {
      src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp',
      alt: { es: 'Dos orcas nadando bajo la superficie del mar, frente a La Ventana', en: 'Two orcas swimming under the surface off La Ventana' },
    },
    destinos: PAQUETES_VENTANA,
    tema: 'mar',
    fotos: [
      { src: '/catalogo/la-ventana-travel-paquete-5-noches.webp', alt: { es: 'Una persona nadando entre un enorme cardumen de rayas', en: 'A person swimming among a huge school of rays' } },
      { src: '/sunbajaexperience/fotos/pangas-en-la-playa.webp', alt: { es: 'Pangas en la arena frente al mar', en: 'Pangas on the sand facing the sea' } },
      { src: '/catalogo/la-ventana-travel-paquete-7-noches.webp', alt: { es: 'Una persona haciendo snorkel entre peces rayados', en: 'A person snorkeling among striped fish' } },
      { src: '/photos/puerto-chale/lobos-marinos-bajo-el-agua.webp', alt: { es: 'Lobos marinos nadan bajo el agua', en: 'Sea lions swim underwater' } },
      { src: '/sunbajaexperience/fotos/salto-al-mar.webp', alt: { es: 'Una persona salta al mar', en: 'A person jumps into the sea' } },
    ],
    fotoFrase: { src: '/sunbajaexperience/fotos/brazos-abiertos-al-mar.webp', alt: { es: 'Un hombre con los brazos abiertos frente al mar', en: 'A man with his arms spread wide facing the sea' } },
    textos: {
      es: {
        slug: 'nado-con-orcas-la-ventana',
        titulo: 'Nado con orcas en La Ventana: cuándo ir y cómo es la salida',
        metaTitulo: 'Nado con orcas en La Ventana, BCS: temporada y cómo es',
        metaDescripcion: 'En La Ventana, Baja California Sur, las orcas vienen todo el año. Cuándo hay más encuentros, cómo es la salida para nadar con ellas y cómo reservarla.',
        respuesta: 'En La Ventana, Baja California Sur, las orcas vienen todo el año, y de finales de abril a julio los encuentros son más frecuentes: es cuando llegan las mobulas. Sales en lancha a buscarlas y, cuando aparecen y el mar lo permite, entras al agua a nadar con ellas.',
        frase: 'Cada salida es una oportunidad más de encontrarlas.',
        datos: [
          { etiqueta: 'Cuándo', valor: 'Todo el año, más de abril a julio' },
          { etiqueta: 'Salida', valor: 'entre las 7:00 y las 8:00 am' },
          { etiqueta: 'Duración', valor: '5 a 6 horas en el mar' },
          { etiqueta: 'Cómo se reserva', valor: 'En paquetes de 5 y 7 noches' },
        ],
        calendario: {
          titulo: 'Qué se ve cada mes en La Ventana',
          filas: [
            { nombre: 'Orcas', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Mobulas', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Delfines y lobos marinos', meses: TODO_EL_ANIO },
          ],
          nota: 'Son animales libres. Los meses marcados son los de más encuentros.',
        },
        secciones: [
          {
            titulo: '¿Por qué hay orcas en La Ventana?',
            parrafos: [
              'La Ventana está frente a la isla Cerralvo, en el Mar de Cortés. Por ese canal pasan cada primavera cardúmenes enormes de mobulas, unas rayas que saltan fuera del agua, y las orcas llegan detrás de ellas a comer.',
              'Quienes las siguen en el Golfo de California cuentan que hay familias de orcas que se quedan aquí todo el año. Por eso pueden aparecer en cualquier mes, y de finales de abril a julio los encuentros son más frecuentes.',
            ],
          },
          {
            titulo: 'El safari marino: ¿cómo es la salida?',
            parrafos: [
              'Sales en lancha entre las 7:00 y las 8:00 am, de La Ventana o Bahía de los Sueños, con gente que conoce estas aguas. Son 5 a 6 horas en el mar, con algo de comer, aguas, refrescos y el equipo de snorkel a bordo.',
              'El día incluye una parada para snorkelear en un arrecife. El resto del tiempo es de búsqueda: orcas, delfines, lobos marinos y lo que el mar traiga ese día.',
            ],
          },
          {
            titulo: '¿Cómo es nadar con ellas?',
            parrafos: [
              'Cuando las orcas aparecen y el mar lo permite, te pones visor y aletas y entras al agua. Tu guía observa cómo se comportan los animales y cómo está el mar, y te avisa cuándo es el momento.',
              'A las ballenas las ves desde la lancha.',
            ],
          },
          {
            titulo: '¿Qué más se ve?',
            parrafos: [
              'Delfines y lobos marinos se ven todo el año. Desde abril llegan las mobulas y las ballenas jorobadas. Hay días en que también aparecen calderones, cachalotes o mantarrayas gigantes.',
            ],
          },
          {
            titulo: '¿Qué llevar?',
            parrafos: ['Lo de un día largo en el mar:'],
            lista: [
              'Traje de baño puesto y una toalla',
              'Bloqueador, gorra y lentes de sol',
              'Un rompevientos: la mañana en la lancha es fresca',
              'Pastillas para el mareo, si te mareas con facilidad',
            ],
          },
        ],
        faq: [
          { q: '¿Qué tan probable es ver orcas?', a: 'Las orcas viven libres y vienen a La Ventana todo el año, así que puedes encontrarlas en cualquier salida. Vas con gente que conoce estas aguas y sabe dónde buscarlas. Y en casi todas las salidas te acompañan delfines o lobos marinos.' },
          { q: '¿Cuál es la mejor temporada para nadar con orcas en La Ventana?', a: 'De finales de abril a julio, cuando las mobulas se juntan frente a La Ventana y las orcas llegan tras ellas. El resto del año también vienen.' },
          { q: '¿Puedo reservar solo la salida de un día?', a: 'El seafari se reserva dentro de los paquetes de 5 y 7 noches, con hotel, traslado del aeropuerto y de 4 a 6 salidas al mar. Con varias salidas tienes varias oportunidades de encontrarlas.' },
          { q: '¿Es seguro nadar con orcas?', a: 'Entras al agua con un guía que conoce a estos animales. Él observa cómo se comportan y cómo está el mar, y te dice cuándo es el momento. Nadas en la superficie, con visor, snorkel y aletas.' },
          { q: '¿Cuánto cuesta nadar con orcas en La Ventana?', a: 'El nado con orcas va dentro de los paquetes de 5 y 7 noches, con hotel, traslado del aeropuerto y de 4 a 6 salidas al mar. El precio es por persona y está al día en cada paquete, en esta página. Reservas en línea con tarjeta.' },
          { q: '¿Necesito saber bucear?', a: 'No hace falta. Nadas en la superficie con visor, snorkel y aletas, y el equipo va incluido.' },
          { q: '¿Qué pasa si hay mal clima?', a: 'Si el mar no deja salir, esa salida se repone otro día de tu estancia.' },
        ],
        producto: {
          titulo: 'Cómo vivirlo',
          texto: 'El seafari va dentro de los paquetes de La Ventana Travel: hotel, traslado del aeropuerto y de 4 a 6 salidas al mar para buscarlas.',
        },
      },
      en: {
        slug: 'swim-with-orcas-la-ventana',
        titulo: 'Swim with orcas in La Ventana: when to go and what the trip is like',
        metaTitulo: 'Swim with Orcas in La Ventana, Baja: Season & What to Expect',
        metaDescripcion: 'Orcas come to La Ventana, Baja California Sur, all year. When encounters peak, what the swim-with-orcas trip is like, and how to book it.',
        respuesta: 'Orcas come to La Ventana, Baja California Sur, all year round, and encounters pick up from late April through July, when the mobula rays arrive. You head out by boat to find them and, when they show up and the sea allows it, you get in the water and swim with them.',
        frase: 'Every trip is one more chance to find them.',
        datos: [
          { etiqueta: 'When', valor: 'All year, most from April to July' },
          { etiqueta: 'Departure', valor: 'between 7:00 and 8:00 am' },
          { etiqueta: 'Length', valor: '5 to 6 hours at sea' },
          { etiqueta: 'How to book', valor: 'In 5- and 7-night packages' },
        ],
        calendario: {
          titulo: 'What you can see each month in La Ventana',
          filas: [
            { nombre: 'Orcas', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Mobula rays', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Dolphins and sea lions', meses: TODO_EL_ANIO },
          ],
          nota: 'These are wild animals. The marked months are the ones with the most encounters.',
        },
        secciones: [
          {
            titulo: 'Why are there orcas in La Ventana?',
            parrafos: [
              'La Ventana faces Cerralvo Island in the Sea of Cortez. Every spring, huge schools of mobula rays, which leap out of the water, move through that channel, and the orcas follow them to feed.',
              'People who track them in the Gulf of California say some orca families stay here all year. That is why they can show up in any month, with encounters most frequent from late April to July.',
            ],
          },
          {
            titulo: 'The ocean safari: what is the trip like?',
            parrafos: [
              'You leave by boat between 7:00 and 8:00 am, from La Ventana or Bahía de los Sueños, with people who know these waters. You spend 5 to 6 hours at sea, with some food, water, soft drinks and snorkeling gear on board.',
              'The day includes a snorkel stop at a reef. The rest of the time you are searching: orcas, dolphins, sea lions and whatever the sea brings that day.',
            ],
          },
          {
            titulo: 'What is swimming with them like?',
            parrafos: [
              'When orcas show up and the sea allows it, you put on a mask and fins and get in the water. Your guide watches how the animals are behaving and what the sea is doing, and tells you when the moment is right.',
              'You watch the whales from the boat.',
            ],
          },
          {
            titulo: 'What else do you see?',
            parrafos: [
              'You see dolphins and sea lions all year. From April the mobula rays and the humpback whales arrive. Some days pilot whales, sperm whales or giant manta rays turn up too.',
            ],
          },
          {
            titulo: 'What should I bring?',
            parrafos: ['What you would take for a long day at sea:'],
            lista: [
              'Your swimsuit on and a towel',
              'Sunscreen, a cap and sunglasses',
              'A windbreaker: mornings on the boat are cool',
              'Motion sickness tablets, if you get seasick easily',
            ],
          },
        ],
        faq: [
          { q: 'How likely am I to see orcas?', a: 'Orcas are wild and come to La Ventana all year, so you can find them on any trip. You go with people who know these waters and where to look. And on almost every trip, dolphins or sea lions join you.' },
          { q: 'When is the best time to see orcas in La Ventana, Baja?', a: 'Late April through July, when the mobula rays gather off La Ventana and the orcas come in after them. They visit the rest of the year too.' },
          { q: 'Can I book just a one-day trip?', a: 'The seafari is booked as part of the 5- and 7-night packages, with the hotel, airport transfers and 4 to 6 trips out to sea. Several trips give you several chances of finding them.' },
          { q: 'Is it safe to swim with orcas in Mexico?', a: 'You get in the water with a guide who knows these animals. The guide watches how they are behaving and what the sea is doing, and tells you when the moment is right. You swim at the surface with a mask, snorkel and fins.' },
          { q: 'How much does it cost to swim with orcas in La Ventana?', a: 'Swimming with orcas is part of the 5- and 7-night packages, with the hotel, airport transfers and 4 to 6 trips out to sea. The price is per person and is up to date on each package, on this page. You book online by card.' },
          { q: 'Do I need to know how to dive?', a: 'Not at all. You swim at the surface with a mask, snorkel and fins, and the gear is included.' },
          { q: 'What happens in bad weather?', a: 'If the sea keeps the boat in, that trip is made up on another day of your stay.' },
        ],
        producto: {
          titulo: 'How to do it',
          texto: 'The seafari is part of La Ventana Travel’s packages: hotel, airport transfers and 4 to 6 trips out to sea to look for them.',
        },
      },
    },
  },

  // 2. Calendario de pesca de La Paz ───────────────────────────────────────────────────────────────────────────
  {
    id: 'calendario-pesca-la-paz',
    sede: 'la-paz',
    actualizado: REVISADO,
    foto: {
      src: '/photos/cliente-dorado.webp',
      alt: { es: 'Un pescador levanta un dorado enorme en la popa de la panga, frente a La Paz', en: 'An angler holds up a huge dorado at the stern of the panga, off La Paz' },
    },
    destinos: [PESCA_LA_PAZ, SEDE_LA_PAZ],
    tema: 'mar',
    fotos: [
      { src: '/catalogo/sal-y-sol-pesca-deportiva.webp', alt: { es: 'Jurel (cola amarilla) recién pescado frente a un acantilado', en: 'Freshly caught yellowtail by a sea cliff' } },
      { src: '/photos/capitanes-con-marlines.webp', alt: { es: 'Dos hombres de mar sostienen un marlín cada uno en la popa de la panga', en: 'Two seamen each hold a marlin at the stern of the panga' } },
      { src: '/photos/yellowtail-pelicanos-bahia.webp', alt: { es: 'De regreso a la bahía, con pelícanos alrededor', en: 'Heading back into the bay, pelicans alongside' } },
      { src: '/photos/joel-dorado.webp', alt: { es: 'El capitán Joel y un pescador levantan entre los dos un dorado enorme', en: 'Captain Joel and an angler lift a huge dorado together' } },
      { src: '/photos/panga-acantilados-rojos.webp', alt: { es: 'La panga Volador III cruza el agua clara frente a acantilados rojos', en: 'The panga Volador III crosses clear water in front of red cliffs' } },
    ],
    fotoFrase: { src: '/photos/panga-rumbo-a-la-pesca.webp', alt: { es: 'La panga Storm, con toldo verde, navega a toda velocidad con tres pescadores a bordo', en: 'The panga Storm, with its green canopy, speeds across the water with three anglers on board' } },
    textos: {
      es: {
        slug: 'calendario-de-pesca-la-paz',
        titulo: 'Calendario de pesca en La Paz: qué se pesca cada mes',
        metaTitulo: 'Calendario y temporada de pesca en La Paz: qué pica cada mes',
        metaDescripcion: 'Temporada de pesca en La Paz, BCS, mes por mes: dorado y marlín de junio a octubre, jurel de enero a abril y sierra al cierre. Se pesca todo el año.',
        respuesta: 'En La Paz se pesca todo el año. La temporada fuerte va de junio a octubre, con dorado y marlín. De enero a abril manda el jurel, y en noviembre y diciembre, la sierra.',
        frase: 'Tu capitán elige el rumbo según cómo amaneció el mar.',
        datos: [
          { etiqueta: 'Temporada fuerte', valor: 'Junio a octubre' },
          { etiqueta: 'Salida', valor: 'Al amanecer, desde {salida:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'Duración', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'A bordo', valor: 'Solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas' },
        ],
        calendario: {
          titulo: 'Qué se pesca en La Paz, mes por mes',
          filas: [
            { nombre: 'Jurel', meses: [1, 2, 3, 4] },
            { nombre: 'Marlín y dorado', meses: [6, 7, 8, 9, 10], fuertes: [6, 7, 8, 9, 10] },
            { nombre: 'Sierra', meses: [11, 12] },
            { nombre: 'Pez gallo', meses: [5, 6, 7], fuente: 'region' },
            { nombre: 'Atún aleta amarilla', meses: [7, 8, 9], fuente: 'region' },
            { nombre: 'Pez vela', meses: [8, 9, 10], fuente: 'region' },
            { nombre: 'Wahoo', meses: [9, 10, 11], fuente: 'region' },
          ],
          nota: 'Las tres primeras filas son el calendario de nuestros capitanes. Las demás vienen de los reportes de pesca de La Paz y se mueven con la temperatura del agua de cada año.',
        },
        secciones: [
          {
            titulo: 'Enero a abril: jurel',
            parrafos: [
              'Con el agua fresca y el mar en calma, el jurel es el pez del invierno. Pelea largo y te va a pedir brazos. En las mismas salidas pican pargo y cabrilla.',
            ],
          },
          {
            titulo: 'Junio a octubre: marlín y dorado',
            parrafos: [
              'Cuando el agua se calienta llegan los peces que saltan. Es la temporada más fuerte del año y por la que más gente viene a La Paz a pescar.',
              'En estos meses también aparecen el atún aleta amarilla, el pez vela y, hacia el otoño, el wahoo.',
            ],
          },
          {
            titulo: 'Noviembre y diciembre: sierra',
            parrafos: [
              'La sierra cierra el año con pesca pareja y mañanas frescas. También sale cochito.',
            ],
          },
          {
            titulo: '¿Cuál es el mejor mes para pescar en La Paz?',
            parrafos: [
              'El del pez que quieres subir a la panga. Para dorado y marlín, de junio a octubre. Para una pelea larga con jurel, de enero a abril. Y si tus fechas ya están fijas, tu capitán elige esa mañana el rumbo según cómo amaneció el mar.',
            ],
          },
          {
            titulo: '¿Necesito licencia de pesca?',
            parrafos: [
              'Sí, y el trámite lo hacemos nosotros: la agregas al reservar y listo. La lleva cada persona que pesca a bordo. Quien solo acompaña va sin ella.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuál es la temporada de pesca en La Paz?', a: 'Se pesca todo el año. La temporada fuerte va de junio a octubre, con dorado y marlín. De enero a abril pica el jurel, y en noviembre y diciembre, la sierra.' },
          { q: '¿Cuánto cuesta un tour de pesca en La Paz?', a: 'La panga privada cuesta {precio:sal-y-sol/pesca-deportiva} con IVA incluido, para {personas:sal-y-sol/pesca-deportiva} personas, y cada persona más paga {extra:sal-y-sol/pesca-deportiva}, hasta {maximo:sal-y-sol/pesca-deportiva} por panga. El precio es el mismo todo el año.' },
          { q: '¿Cuándo es la temporada de dorado en La Paz?', a: 'De junio a octubre. Son los mismos meses del marlín y los más fuertes del año.' },
          { q: '¿Se puede pescar en La Paz en invierno?', a: 'Sí. De enero a abril pica el jurel, con pargo y cabrilla, y en noviembre y diciembre, la sierra. Salimos los 365 días del año.' },
          { q: '¿Cuánto dura una salida de pesca?', a: '{duracion:sal-y-sol/pesca-deportiva}. Sales al amanecer de {salida:sal-y-sol/pesca-deportiva} y eliges la hora al reservar.' },
          { q: '¿Cuántas personas caben en la panga?', a: 'Hay pangas para hasta 3 y para hasta {maximo:sal-y-sol/pesca-deportiva} personas. En cualquiera va solo tu grupo.' },
          { q: '¿Qué pasa si hay mal clima?', a: 'Eliges tú: cambias la fecha o recibes el reembolso completo. Aplica cuando la capitanía de puerto o tu capitán deciden que el mar no está para salir.' },
        ],
        producto: {
          titulo: 'Elige tu fecha',
          texto: 'Sales en panga privada con un capitán de La Paz. El precio y los días libres están en su página.',
        },
      },
      en: {
        slug: 'la-paz-fishing-calendar',
        titulo: 'La Paz fishing calendar: what’s biting each month',
        metaTitulo: 'La Paz Fishing Calendar & Seasons: What’s Biting Each Month',
        metaDescripcion: 'La Paz fishing seasons month by month: dorado and marlin June to October, yellowtail January to April, sierra at year’s end. You can fish all year.',
        respuesta: 'You can fish La Paz all year. Peak season runs from June to October, with dorado (mahi mahi) and marlin. January to April belongs to yellowtail, and November and December to sierra.',
        frase: 'Your captain picks the heading by how the sea looks that morning.',
        datos: [
          { etiqueta: 'Peak season', valor: 'June to October' },
          { etiqueta: 'Departure', valor: 'At dawn, from {salida:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'Length', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'On board', valor: 'Just your group, up to {maximo:sal-y-sol/pesca-deportiva} people' },
        ],
        calendario: {
          titulo: 'What you catch in La Paz, month by month',
          filas: [
            { nombre: 'Yellowtail', meses: [1, 2, 3, 4] },
            { nombre: 'Marlin and dorado', meses: [6, 7, 8, 9, 10], fuertes: [6, 7, 8, 9, 10] },
            { nombre: 'Sierra', meses: [11, 12] },
            { nombre: 'Roosterfish', meses: [5, 6, 7], fuente: 'region' },
            { nombre: 'Yellowfin tuna', meses: [7, 8, 9], fuente: 'region' },
            { nombre: 'Sailfish', meses: [8, 9, 10], fuente: 'region' },
            { nombre: 'Wahoo', meses: [9, 10, 11], fuente: 'region' },
          ],
          nota: 'The first three rows are our captains’ calendar. The rest come from La Paz fishing reports and shift with each year’s water temperature.',
        },
        secciones: [
          {
            titulo: 'January to April: yellowtail',
            parrafos: [
              'With cool water and calm seas, yellowtail is the winter fish. It fights long and it will work your arms. Snapper and cabrilla bite on the same trips.',
            ],
          },
          {
            titulo: 'June to October: marlin and dorado',
            parrafos: [
              'When the water warms up, the jumpers arrive. This is the strongest season of the year and the one most people come to La Paz to fish.',
              'Yellowfin tuna and sailfish show up in these months too and, toward fall, wahoo.',
            ],
          },
          {
            titulo: 'November and December: sierra',
            parrafos: [
              'Sierra closes out the year with steady fishing and cool mornings. Triggerfish (cochito) bites too.',
            ],
          },
          {
            titulo: 'What is the best month to fish in La Paz?',
            parrafos: [
              'The month of the fish you want to bring aboard. For dorado and marlin, June to October. For a long fight with yellowtail, January to April. And if your dates are already set, your captain picks the heading that morning based on the sea.',
            ],
          },
          {
            titulo: 'Do I need a fishing license?',
            parrafos: [
              'Yes, and we handle the paperwork: you add it when you book and that is it. Every person fishing on board carries one. Anyone just riding along goes without.',
            ],
          },
        ],
        faq: [
          { q: 'When is fishing season in La Paz?', a: 'You can fish all year. Peak season runs from June to October, with dorado and marlin. January to April is yellowtail, and November and December, sierra.' },
          { q: 'How much does a fishing charter in La Paz cost?', a: 'The private panga costs {precio:sal-y-sol/pesca-deportiva}, tax included, for {personas:sal-y-sol/pesca-deportiva} people, and each additional person pays {extra:sal-y-sol/pesca-deportiva}, up to {maximo:sal-y-sol/pesca-deportiva} per panga. The price is the same all year.' },
          { q: 'When is dorado (mahi mahi) season in La Paz?', a: 'June to October. Those are the marlin months too, and the strongest of the year.' },
          { q: 'Can you fish La Paz in winter?', a: 'Yes. Yellowtail bites from January to April, with snapper and cabrilla, and sierra in November and December. We go out 365 days a year.' },
          { q: 'How long is a fishing trip?', a: '{duracion:sal-y-sol/pesca-deportiva}. You leave {salida:sal-y-sol/pesca-deportiva} at dawn and choose your time when you book.' },
          { q: 'How many people fit on the panga?', a: 'There are pangas for up to 3 and for up to {maximo:sal-y-sol/pesca-deportiva} people. On either one, only your group is on board.' },
          { q: 'What happens in bad weather?', a: 'Your call: a new date or a full refund. That applies whenever the port captain or your captain decides the sea is not fit to go out.' },
        ],
        producto: {
          titulo: 'Pick your date',
          texto: 'You go out on a private panga with a La Paz captain. Prices and open days are on its page.',
        },
      },
    },
  },

  // 3. Temporada de ballena gris en Bahía Magdalena ────────────────────────────────────────────────────────────
  {
    id: 'ballena-gris-bahia-magdalena',
    sede: 'puerto-chale',
    actualizado: REVISADO,
    foto: {
      src: '/photos/puerto-chale/ballenas-junto-a-la-panga.webp',
      alt: { es: 'Dos ballenas grises nadan pegadas a la panga en Bahía Magdalena mientras una pasajera las toca', en: 'Two gray whales swim right beside the panga on Magdalena Bay while a passenger reaches out to them' },
    },
    destinos: [BALLENAS_CHALE, SEDE_CHALE],
    tema: 'mar',
    fotos: [
      { src: '/photos/puerto-chale/ballena-y-la-sierra.webp', alt: { es: 'Una ballena gris nada junto a la panga, con la sierra al fondo', en: 'A gray whale swims beside the panga, with the mountains behind' } },
      { src: '/photos/puerto-chale/ballena-de-cerca.webp', alt: { es: 'El lomo de una ballena gris, cubierto de percebes, junto a la panga', en: 'The barnacled back of a gray whale beside the panga' } },
      { src: '/photos/puerto-chale/ballena-bajo-el-agua.webp', alt: { es: 'Una ballena gris pasa bajo el agua, a un lado de la panga', en: 'A gray whale passes under the water beside the panga' } },
      { src: '/photos/puerto-chale/cristian-panga-atardecer.webp', alt: { es: 'Cristian saluda desde su panga al atardecer, con el sol cayendo detrás de la isla', en: 'Cristian waves from his panga at sunset, with the sun going down behind the island' } },
      { src: '/photos/puerto-chale/lobos-marinos-en-la-superficie.webp', alt: { es: 'Lobos marinos asoman en la superficie del mar', en: 'Sea lions pop up at the surface' } },
    ],
    fotoFrase: { src: '/photos/puerto-chale/ballena-asomada.webp', alt: { es: 'Una ballena gris asoma la cabeza frente a la isla', en: 'A gray whale lifts its head out of the water in front of the island' } },
    textos: {
      es: {
        slug: 'temporada-ballena-gris-bahia-magdalena',
        titulo: 'Temporada de ballena gris en Bahía Magdalena: cuándo ir',
        metaTitulo: 'Temporada de ballena gris en Bahía Magdalena: cuándo ir',
        metaDescripcion: 'De enero a marzo la ballena gris está en Bahía Magdalena con sus crías y se acerca a las pangas. Cómo es la salida desde Puerto Chale, a 2 h de La Paz.',
        respuesta: 'La ballena gris está en Bahía Magdalena de enero a marzo. Viaja desde el Ártico para tener a sus crías en estas aguas tranquilas, y aquí se deja ver de cerca. Sales de Puerto Chale, a unas 2 horas de La Paz, en un recorrido de {duracion:piratas-adventures/avistamiento-ballenas}.',
        frase: 'Aquí las ballenas se acercan solas a la panga.',
        datos: [
          { etiqueta: 'Temporada', valor: 'Enero a marzo' },
          { etiqueta: 'Sale de', valor: 'Puerto Chale, Bahía Magdalena' },
          { etiqueta: 'Recorrido', valor: '{duracion:piratas-adventures/avistamiento-ballenas} en panga' },
          { etiqueta: 'Desde La Paz', valor: 'De 1 h 40 min a 2 h por carretera' },
        ],
        calendario: {
          titulo: 'Qué hay cada mes en Puerto Chale',
          filas: [
            { nombre: 'Ballena gris', meses: [1, 2, 3], fuertes: [1, 2, 3] },
            { nombre: 'Ballena jorobada', meses: [10, 11, 12] },
            { nombre: 'Safari marino', meses: [10, 11, 12] },
            { nombre: 'Pesca deportiva', meses: TODO_EL_ANIO },
          ],
          nota: 'La ballena jorobada pasa a finales de año y sus meses se mueven un poco con cada temporada.',
        },
        secciones: [
          {
            titulo: '¿Por qué viene la ballena gris a Bahía Magdalena?',
            parrafos: [
              'Cada otoño la ballena gris deja las aguas frías del Ártico, donde come durante el verano, y baja pegada a la costa hasta las lagunas de Baja California Sur. El viaje de ida y vuelta suma entre 16,000 y 19,000 kilómetros, uno de los más largos de cualquier mamífero.',
              'Bahía Magdalena es la más sureña de esas lagunas. Sus aguas son tranquilas y poco profundas, y ahí nacen las crías, que miden unos 4.5 metros al nacer y pasan varios meses junto a su madre.',
            ],
          },
          {
            titulo: '¿Qué se ve en una salida?',
            parrafos: [
              'Sales en la panga de una familia de pescadores de Puerto Chale. De enero a marzo las madres están en la bahía con sus crías y se acercan a la panga: ves de cerca el lomo cubierto de percebes y escuchas el soplo.',
              'Un adulto llega a medir 15 metros, más que la panga en la que vas.',
            ],
          },
          {
            titulo: '¿Cuánto dura y cuántos caben?',
            parrafos: [
              'El recorrido que reservas en línea dura {duracion:piratas-adventures/avistamiento-ballenas}. Si quieres quedarte más tiempo con ellas, hay recorridos de 3 y 4 horas que se piden por WhatsApp.',
              'El precio cubre de 1 a {personas:piratas-adventures/avistamiento-ballenas} personas y caben hasta {maximo:piratas-adventures/avistamiento-ballenas}, con un cargo por cada persona extra. Los niños son bienvenidos.',
            ],
          },
          {
            titulo: '¿Qué llevar?',
            parrafos: ['En invierno la mañana en el Pacífico es fría y con viento:'],
            lista: [
              'Chamarra o rompevientos',
              'Bloqueador y gorra',
              'Cámara o teléfono con correa: las ballenas se acercan mucho',
              'Efectivo: Puerto Chale es un pueblo pequeño',
            ],
          },
          {
            titulo: '¿Y fuera de la temporada?',
            parrafos: [
              'De octubre a diciembre sale el safari marino, {duracion:piratas-adventures/safari-marino} entre islas con lobos marinos y peces, y a finales de año pasa la ballena jorobada. La pesca deportiva es todo el año.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuánto cuesta ver ballenas en Puerto Chale?', a: 'El avistamiento de {duracion:piratas-adventures/avistamiento-ballenas} cuesta {precio:piratas-adventures/avistamiento-ballenas} con IVA incluido. El precio es por la panga para tu grupo, de 1 a {personas:piratas-adventures/avistamiento-ballenas} personas, y cada persona extra paga {extra:piratas-adventures/avistamiento-ballenas}, hasta {maximo:piratas-adventures/avistamiento-ballenas}.' },
          { q: '¿Cuándo es la temporada de ballena gris en Bahía Magdalena?', a: 'De enero a marzo, cuando la ballena gris entra a la bahía a tener a sus crías.' },
          { q: '¿Se puede tocar a las ballenas?', a: 'Hay días en que las ballenas grises llegan solas hasta la panga y se quedan a un brazo de distancia. Se acercan cuando ellas quieren; nadie las persigue.' },
          { q: '¿Cómo llego a Puerto Chale?', a: 'Por carretera. Desde La Paz son entre 1 hora 40 minutos y 2 horas. La ruta completa está en la guía de cómo llegar a Puerto Chale.' },
          { q: '¿Pueden ir niños?', a: 'Sí. Los niños son bienvenidos en el avistamiento de ballenas.' },
          { q: '¿Qué pasa si hay mal clima?', a: 'Si el mal clima impide salir, recibes el reembolso completo. Y si te cambian los planes, puedes mover la fecha con al menos 48 horas de anticipación.' },
        ],
        producto: {
          titulo: 'Reserva tu salida',
          texto: 'Te lleva Piratas Adventures, una familia de Puerto Chale con más de cinco generaciones en esta bahía.',
        },
      },
      en: {
        slug: 'gray-whale-season-magdalena-bay',
        titulo: 'Gray whale season in Magdalena Bay: when to go',
        metaTitulo: 'Gray Whale Season in Magdalena Bay, Baja: When to Go',
        metaDescripcion: 'From January to March gray whales are in Magdalena Bay with their calves and swim up to the pangas. The trip from Puerto Chale, 2 hours from La Paz.',
        respuesta: 'Gray whales are in Magdalena Bay from January to March. They travel from the Arctic to give birth in these calm waters, and here you see them up close. You leave from Puerto Chale, about 2 hours from La Paz, on a trip of {duracion:piratas-adventures/avistamiento-ballenas}.',
        frase: 'Here the whales swim up to the panga on their own.',
        datos: [
          { etiqueta: 'Season', valor: 'January to March' },
          { etiqueta: 'Leaves from', valor: 'Puerto Chale, Magdalena Bay' },
          { etiqueta: 'Trip', valor: '{duracion:piratas-adventures/avistamiento-ballenas} by panga' },
          { etiqueta: 'From La Paz', valor: '1 h 40 min to 2 h by road' },
        ],
        calendario: {
          titulo: 'What’s on each month in Puerto Chale',
          filas: [
            { nombre: 'Gray whales', meses: [1, 2, 3], fuertes: [1, 2, 3] },
            { nombre: 'Humpback whales', meses: [10, 11, 12] },
            { nombre: 'Marine safari', meses: [10, 11, 12] },
            { nombre: 'Sportfishing', meses: TODO_EL_ANIO },
          ],
          nota: 'Humpback whales pass through late in the year, and their months shift a little each season.',
        },
        secciones: [
          {
            titulo: 'Why do gray whales come to Magdalena Bay?',
            parrafos: [
              'Every fall, gray whales leave the cold Arctic waters where they feed all summer and follow the coast down to the lagoons of Baja California Sur. The round trip adds up to 10,000 to 12,000 miles (16,000 to 19,000 km), one of the longest of any mammal.',
              'Magdalena Bay is the southernmost of those lagoons. Its waters are calm and shallow, and that is where the calves are born, about 15 feet (4.5 m) long. They spend several months beside their mothers.',
            ],
          },
          {
            titulo: 'What do you see on a trip?',
            parrafos: [
              'You go out on the panga of a fishing family from Puerto Chale. From January to March the mothers are in the bay with their calves and come up to the panga: you see the barnacle-covered back up close and hear the blow.',
              'An adult grows up to 50 feet (15 m), longer than the panga you are on.',
            ],
          },
          {
            titulo: 'How long is it, and how many fit?',
            parrafos: [
              'The trip you book online lasts {duracion:piratas-adventures/avistamiento-ballenas}. If you want more time with them, there are 3- and 4-hour trips you can ask for on WhatsApp.',
              'The price covers 1 to {personas:piratas-adventures/avistamiento-ballenas} people and up to {maximo:piratas-adventures/avistamiento-ballenas} fit, with a charge for each extra person. Children are welcome.',
            ],
          },
          {
            titulo: 'What should I bring?',
            parrafos: ['In winter, mornings on the Pacific are cold and windy:'],
            lista: [
              'A jacket or windbreaker',
              'Sunscreen and a cap',
              'A camera or phone on a strap: the whales come very close',
              'Cash: Puerto Chale is a small village',
            ],
          },
          {
            titulo: 'What about outside the season?',
            parrafos: [
              'From October to December the marine safari runs, {duracion:piratas-adventures/safari-marino} among the islands with sea lions and fish, and humpback whales pass through late in the year. Sportfishing runs all year.',
            ],
          },
        ],
        faq: [
          { q: 'How much does whale watching in Puerto Chale cost?', a: 'The whale watching trip lasts {duracion:piratas-adventures/avistamiento-ballenas} and costs {precio:piratas-adventures/avistamiento-ballenas}, tax included. The price is for the panga for your group, 1 to {personas:piratas-adventures/avistamiento-ballenas} people, and each extra person pays {extra:piratas-adventures/avistamiento-ballenas}, up to {maximo:piratas-adventures/avistamiento-ballenas}.' },
          { q: 'When is gray whale season in Magdalena Bay?', a: 'January to March, when gray whales enter the bay to give birth.' },
          { q: 'Can you touch the whales?', a: 'Some days the gray whales swim right up to the panga on their own and stay within arm’s reach. They come over when they want to; nobody chases them.' },
          { q: 'How do I get to Puerto Chale?', a: 'By road. From La Paz it is between 1 hour 40 minutes and 2 hours. The full route is in the guide on how to get to Puerto Chale.' },
          { q: 'Can children come?', a: 'Yes. Children are welcome on the whale watching trip.' },
          { q: 'What happens in bad weather?', a: 'If bad weather keeps the boat in, you get a full refund. And if your plans change, you can move your date with at least 48 hours’ notice.' },
        ],
        producto: {
          titulo: 'Book your trip',
          texto: 'Piratas Adventures takes you out: a Puerto Chale family with more than five generations on this bay.',
        },
      },
    },
  },

  // 4. Cómo llegar a Puerto Chale ──────────────────────────────────────────────────────────────────────────────
  {
    id: 'como-llegar-puerto-chale',
    sede: 'puerto-chale',
    actualizado: REVISADO,
    foto: {
      src: '/photos/puerto-chale/panga-entre-islas.webp',
      alt: { es: 'Una panga navega entre las islas de Bahía Magdalena, frente a Puerto Chale', en: 'A panga runs between the islands of Magdalena Bay, off Puerto Chale' },
    },
    destinos: [SEDE_CHALE, BALLENAS_CHALE],
    tema: 'traslado',
    fotos: [
      { src: '/photos/puerto-chale/ballena-y-la-sierra.webp', alt: { es: 'Una ballena gris nada junto a la panga, con la sierra al fondo', en: 'A gray whale swims beside the panga, with the mountains behind' } },
      { src: '/photos/puerto-chale/arrecife-con-peces.webp', alt: { es: 'Peces sobre el arrecife, con el sol entrando por la superficie', en: 'Fish over the reef, with sunlight coming through the surface' } },
      { src: '/photos/puerto-chale/pesca-submarina-en-la-panga.webp', alt: { es: 'Buzos en neopreno suben su pesca a la panga', en: 'Divers in wetsuits bring their catch aboard the panga' } },
      { src: '/photos/puerto-chale/lobos-marinos-en-la-superficie.webp', alt: { es: 'Lobos marinos asoman en la superficie del mar', en: 'Sea lions pop up at the surface' } },
    ],
    fotoFrase: { src: '/photos/puerto-chale/cristian-panga-atardecer.webp', alt: { es: 'Cristian saluda desde su panga al atardecer, con el sol cayendo detrás de la isla', en: 'Cristian waves from his panga at sunset, with the sun going down behind the island' } },
    textos: {
      es: {
        slug: 'como-llegar-a-puerto-chale',
        titulo: 'Cómo llegar a Puerto Chale desde La Paz y Los Cabos',
        metaTitulo: 'Cómo llegar a Puerto Chale desde La Paz y Los Cabos',
        metaDescripcion: 'Ruta a Puerto Chale, Bahía Magdalena: desde La Paz son de 1 h 40 min a 2 h por la Transpeninsular, con desviación en Santa Rita, kilómetro 157.',
        respuesta: 'Puerto Chale está a entre 1 hora 40 minutos y 2 horas de La Paz por carretera. Tomas la Transpeninsular hacia Ciudad Constitución y te desvías en Santa Rita, en el kilómetro 157. De ahí son unos 23 kilómetros hasta el muelle.',
        frase: 'De La Paz al muelle son dos horas de carretera.',
        datos: [
          { etiqueta: 'Desde La Paz', valor: 'De 1 h 40 min a 2 h' },
          { etiqueta: 'Desviación', valor: 'Santa Rita, km 157' },
          { etiqueta: 'Último tramo', valor: 'Unos 23 km hasta el muelle' },
          { etiqueta: 'Punto de salida', valor: 'Te lo mandamos por WhatsApp' },
        ],
        secciones: [
          {
            titulo: 'Desde La Paz',
            parrafos: [
              'Sal de La Paz por la carretera Transpeninsular (México 1) rumbo al norte, hacia Ciudad Constitución. En el kilómetro 157 está Santa Rita: ahí tomas la desviación a la izquierda, hacia la costa del Pacífico.',
              'Desde el entronque son unos 23 kilómetros hasta el muelle de Puerto Chale, que es el centro del pueblo y de donde salen las pangas.',
            ],
          },
          {
            titulo: 'Desde Los Cabos',
            parrafos: [
              'Primero llegas a La Paz, a unas 2 horas de Cabo San Lucas por la carretera que pasa por Todos Santos, y de ahí sigues la ruta de arriba. En total son unas 4 horas de camino, así que lo más cómodo es dormir en La Paz la noche anterior y llegar descansado.',
            ],
          },
          {
            titulo: 'Desde Ciudad Constitución',
            parrafos: [
              'Baja hacia el sur por la Transpeninsular hasta Santa Rita y toma la misma desviación a Puerto Chale, ahora a la derecha.',
            ],
          },
          {
            titulo: 'Antes de salir',
            parrafos: ['Puerto Chale es un pueblo de pescadores pequeño, así que conviene llegar con todo resuelto:'],
            lista: [
              'Sal con el tanque lleno',
              'Lleva efectivo',
              'Sal con tiempo: las salidas al mar son por la mañana',
              'Escríbenos por WhatsApp y te decimos cómo está el último tramo y el punto exacto de salida',
            ],
          },
        ],
        faq: [
          { q: '¿Qué tan lejos está Bahía Magdalena de Los Cabos?', a: 'Unas 4 horas por carretera: 2 de Cabo San Lucas a La Paz y cerca de 2 más hasta Puerto Chale.' },
          { q: '¿Cuánto tiempo se hace de La Paz a Puerto Chale?', a: 'Entre 1 hora 40 minutos y 2 horas por carretera.' },
          { q: '¿Dónde está la desviación a Puerto Chale?', a: 'En Santa Rita, en el kilómetro 157 de la carretera Transpeninsular, entre La Paz y Ciudad Constitución. De ahí son unos 23 kilómetros hasta el muelle.' },
          { q: '¿Se puede ir y volver el mismo día desde La Paz?', a: 'Sí. El avistamiento de ballenas dura {duracion:piratas-adventures/avistamiento-ballenas}, así que saliendo temprano de La Paz estás de vuelta el mismo día.' },
          { q: '¿Dónde queda Puerto Chale?', a: 'En la orilla de Bahía Almejas, la parte sur de Bahía Magdalena, del lado del Pacífico de Baja California Sur, dentro del municipio de La Paz.' },
        ],
        producto: {
          titulo: 'Qué te espera al llegar',
          texto: 'Desde el muelle sales a ver ballenas, al safari marino o a pescar en el Pacífico con una familia del pueblo.',
        },
      },
      en: {
        slug: 'how-to-get-to-puerto-chale',
        titulo: 'How to get to Puerto Chale from La Paz and Los Cabos',
        metaTitulo: 'How to Get to Puerto Chale from La Paz and Los Cabos',
        metaDescripcion: 'The route to Puerto Chale, Magdalena Bay: 1 h 40 min to 2 h from La Paz on the Transpeninsular Highway, turning off at Santa Rita, kilometer 157.',
        respuesta: 'Puerto Chale is between 1 hour 40 minutes and 2 hours from La Paz by road. You take the Transpeninsular Highway toward Ciudad Constitución and turn off at Santa Rita, at kilometer 157. From there it is about 23 km (14 miles) to the pier.',
        frase: 'From La Paz to the pier it is a two-hour drive.',
        datos: [
          { etiqueta: 'From La Paz', valor: '1 h 40 min to 2 h' },
          { etiqueta: 'Turnoff', valor: 'Santa Rita, km 157' },
          { etiqueta: 'Last stretch', valor: 'About 23 km (14 mi) to the pier' },
          { etiqueta: 'Meeting point', valor: 'We send it on WhatsApp' },
        ],
        secciones: [
          {
            titulo: 'From La Paz',
            parrafos: [
              'Leave La Paz on the Transpeninsular Highway (Mexico 1) heading north, toward Ciudad Constitución. Santa Rita is at kilometer 157: take the turnoff there to the left, toward the Pacific coast.',
              'From the junction it is about 23 km (14 miles) to the Puerto Chale pier, the heart of the village and where the pangas leave from.',
            ],
          },
          {
            titulo: 'From Los Cabos',
            parrafos: [
              'First you drive to La Paz, about 2 hours from Cabo San Lucas on the highway through Todos Santos, and from there you follow the route above. It adds up to about 4 hours on the road, so the comfortable way is to sleep in La Paz the night before and arrive rested.',
            ],
          },
          {
            titulo: 'From Ciudad Constitución',
            parrafos: [
              'Head south on the Transpeninsular Highway to Santa Rita and take the same turnoff to Puerto Chale, this time on your right.',
            ],
          },
          {
            titulo: 'Before you leave',
            parrafos: ['Puerto Chale is a small fishing village, so it pays to arrive with everything sorted:'],
            lista: [
              'Leave with a full tank',
              'Bring cash',
              'Leave early: boats go out in the morning',
              'Message us on WhatsApp and we will tell you how the last stretch is and the exact meeting point',
            ],
          },
        ],
        faq: [
          { q: 'How far is Magdalena Bay from Cabo?', a: 'About 4 hours by road: 2 from Cabo San Lucas to La Paz, and close to 2 more to Puerto Chale.' },
          { q: 'How long is the drive from La Paz to Puerto Chale?', a: 'Between 1 hour 40 minutes and 2 hours by road.' },
          { q: 'Where is the turnoff to Puerto Chale?', a: 'At Santa Rita, kilometer 157 of the Transpeninsular Highway, between La Paz and Ciudad Constitución. From there it is about 23 km (14 miles) to the pier.' },
          { q: 'Can I do it as a day trip from La Paz?', a: 'Yes. The whale watching trip lasts {duracion:piratas-adventures/avistamiento-ballenas}, so if you leave La Paz early you are back the same day.' },
          { q: 'Where is Puerto Chale?', a: 'On the shore of Bahía Almejas, the southern end of Magdalena Bay, on the Pacific side of Baja California Sur, in the municipality of La Paz.' },
        ],
        producto: {
          titulo: 'What is waiting when you arrive',
          texto: 'From the pier you go out to see whales, on a marine safari, or fishing on the Pacific with a family from the village.',
        },
      },
    },
  },

  // 5. Qué hacer en La Ventana ─────────────────────────────────────────────────────────────────────────────────
  {
    id: 'que-hacer-la-ventana',
    sede: 'la-ventana',
    actualizado: ACTUALIZADO,
    foto: {
      src: '/catalogo/la-ventana-travel-paquete-5-noches.webp',
      alt: { es: 'Una persona nada entre un enorme cardumen de mobulas frente a La Ventana', en: 'A swimmer among a huge school of mobula rays off La Ventana' },
    },
    destinos: [SEDE_VENTANA, ...PAQUETES_VENTANA],
    tema: 'estancia',
    fotos: [
      { src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp', alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' } },
      { src: '/catalogo/la-ventana-travel-pesca-con-mosca.webp', alt: { es: 'Un joven peleando un pez con la caña doblada, en alta mar', en: 'A young angler fighting a fish with a bent rod, out at sea' } },
      { src: '/sunbajaexperience/fotos/cardones-al-atardecer.webp', alt: { es: 'Cardones altos contra el cielo del atardecer', en: 'Tall cardon cacti against the sunset sky' } },
      { src: '/sunbajaexperience/fotos/cardon-junto-al-mar.webp', alt: { es: 'Un cardón junto al mar', en: 'A cardon cactus by the sea' } },
      { src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp', alt: { es: 'Vista aérea del Hotel Casa Arrecife con el mar de La Ventana al fondo', en: 'Aerial view of Hotel Casa Arrecife with the La Ventana sea behind it' } },
    ],
    fotoFrase: { src: '/sunbajaexperience/fotos/salto-al-mar.webp', alt: { es: 'Una persona salta al mar', en: 'A person jumps into the sea' } },
    textos: {
      es: {
        slug: 'que-hacer-en-la-ventana',
        titulo: 'Qué hacer en La Ventana, Baja California Sur',
        metaTitulo: 'Qué hacer en La Ventana, BCS: orcas, snorkel, viento y más',
        metaDescripcion: 'Qué hacer en La Ventana, Baja California Sur: seafari de orcas y mobulas, snorkel, pesca con mosca, kitesurf en invierno y aguas termales en la playa.',
        respuesta: 'La Ventana es un pueblo de playa a unos 45 minutos de La Paz, frente a la isla Cerralvo. Aquí sales al mar a buscar orcas y mobulas, haces snorkel y pescas con mosca. En invierno llega el viento, y con él, el kitesurf.',
        frase: 'Un pueblo de playa con orcas enfrente.',
        datos: [
          { etiqueta: 'Dónde queda', valor: 'A unos 45 min de La Paz' },
          { etiqueta: 'En el mar', valor: 'Orcas, mobulas, delfines, snorkel' },
          { etiqueta: 'Viento', valor: 'De noviembre a marzo' },
          { etiqueta: 'Para quedarte', valor: 'Paquetes de 5 y 7 noches con hotel' },
        ],
        calendario: {
          titulo: 'Cuándo ir a La Ventana',
          filas: [
            { nombre: 'Orcas', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Mobulas', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Viento para kitesurf', meses: [11, 12, 1, 2, 3], fuente: 'region' },
          ],
          nota: 'El viento y las mobulas son datos generales de la zona y se mueven un poco cada año.',
        },
        secciones: [
          {
            titulo: 'Salir al mar: el seafari',
            parrafos: [
              'Es la salida por la que más gente viene. Son 5 a 6 horas en lancha buscando orcas, delfines y lobos marinos, con una parada de snorkel en un arrecife. Cuando aparecen orcas y el mar lo permite, nadas con ellas.',
              'Va dentro de los paquetes de 5 y 7 noches, que traen de 4 a 6 salidas.',
            ],
          },
          {
            titulo: 'Pesca con mosca',
            parrafos: [
              'Un día completo en panga para un grupo de hasta {maximo:la-ventana-travel/pesca-con-mosca} personas, contando a quien pesca. El precio es por día y por grupo, y a bordo hay comida ligera y equipo de snorkel.',
            ],
          },
          {
            titulo: 'Kitesurf y viento',
            parrafos: [
              'De noviembre a marzo sopla el viento del norte casi todas las tardes, y La Ventana se llena de velas. Es uno de los lugares más conocidos de México para kitesurf y windsurf, con escuelas a lo largo de la playa.',
              'Las mañanas de invierno suelen ser tranquilas, buenas para salir al mar antes de que entre el viento.',
            ],
          },
          {
            titulo: 'Aguas termales en la playa',
            parrafos: [
              'Al norte del pueblo, en la playa de Agua Caliente, el agua caliente brota bajo la arena. Con marea baja cavas una poza a la orilla del mar y te queda una tina natural.',
            ],
          },
          {
            titulo: 'Cómo llegar',
            parrafos: [
              'Desde La Paz son unos 45 minutos por carretera, y desde Cabo San Lucas unas 2 horas y media. Si vienes en paquete, el traslado redondo del aeropuerto ya va incluido.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuál es la mejor época para ir a La Ventana?', a: 'La que vaya con tu plan. De finales de abril a julio hay más encuentros con orcas y mobulas. De noviembre a marzo es la temporada de viento para kitesurf.' },
          { q: '¿A cuánto está La Ventana de La Paz?', a: 'A unos 45 minutos por carretera.' },
          { q: '¿Dónde me quedo?', a: 'Los paquetes incluyen el Hotel Casa Arrecife: seis estudios para 2 personas, con cama king size, a 1 km de la playa.' },
          { q: '¿Se puede ir con niños?', a: 'Sí, niños de cualquier edad son bienvenidos. Cada estudio del hotel es para 2 personas, sin camas extra, así que una familia reserva los estudios que necesite.' },
        ],
        producto: {
          titulo: 'Reserva en La Ventana',
          texto: 'Con La Ventana Travel reservas la pesca con mosca por día o un paquete con hotel, traslado y salidas al mar.',
        },
      },
      en: {
        slug: 'things-to-do-in-la-ventana',
        titulo: 'Things to do in La Ventana, Baja California Sur',
        metaTitulo: 'Things to Do in La Ventana, Baja: Orcas, Snorkel, Kiting',
        metaDescripcion: 'Things to do in La Ventana, Baja California Sur: orca and mobula ray seafaris, snorkeling, fly fishing, winter kiteboarding and beach hot springs.',
        respuesta: 'La Ventana is a beach village about 45 minutes from La Paz, facing Cerralvo Island. Here you head out to sea to look for orcas and mobula rays, snorkel, and fly fish. In winter the wind arrives, and kiteboarding with it.',
        frase: 'A beach village with orcas out front.',
        datos: [
          { etiqueta: 'Where it is', valor: 'About 45 min from La Paz' },
          { etiqueta: 'At sea', valor: 'Orcas, mobula rays, dolphins, snorkeling' },
          { etiqueta: 'Wind', valor: 'November to March' },
          { etiqueta: 'To stay', valor: '5- and 7-night packages with hotel' },
        ],
        calendario: {
          titulo: 'When to go to La Ventana',
          filas: [
            { nombre: 'Orcas', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Mobula rays', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Wind for kiteboarding', meses: [11, 12, 1, 2, 3], fuente: 'region' },
          ],
          nota: 'Wind and mobula ray months are general data for the area and shift a little each year.',
        },
        secciones: [
          {
            titulo: 'Out at sea: the seafari',
            parrafos: [
              'This is the trip most people come for. It is 5 to 6 hours by boat looking for orcas, dolphins and sea lions, with a snorkel stop at a reef. When orcas show up and the sea allows it, you swim with them.',
              'It comes with the 5- and 7-night packages, which include 4 to 6 trips.',
            ],
          },
          {
            titulo: 'Fly fishing',
            parrafos: [
              'A full day on a panga for a group of up to {maximo:la-ventana-travel/pesca-con-mosca} people, counting the angler. The price is per day and per group, with a light meal and snorkeling gear on board.',
            ],
          },
          {
            titulo: 'Kiteboarding and wind',
            parrafos: [
              'From November to March the north wind blows most afternoons and La Ventana fills with kites. It is one of the best-known spots in Mexico for kiteboarding and windsurfing, with schools all along the beach.',
              'Winter mornings are usually calm, good for getting out to sea before the wind picks up.',
            ],
          },
          {
            titulo: 'Hot springs on the beach',
            parrafos: [
              'North of the village, at Agua Caliente beach, hot water seeps up under the sand. At low tide you dig a pool at the water’s edge and you have a natural hot tub.',
            ],
          },
          {
            titulo: 'Getting there',
            parrafos: [
              'It is about 45 minutes by road from La Paz and about 2.5 hours from Cabo San Lucas. If you come on a package, round-trip airport transfers are already included.',
            ],
          },
        ],
        faq: [
          { q: 'When is the best time to visit La Ventana?', a: 'Whenever fits your plan. Late April to July brings the most orca and mobula ray encounters. November to March is the wind season for kiteboarding.' },
          { q: 'How far is La Ventana from La Paz?', a: 'About 45 minutes by road.' },
          { q: 'Where do I stay?', a: 'Packages include Hotel Casa Arrecife: six studios for 2 people each, with a king-size bed, 1 km from the beach.' },
          { q: 'Can I come with children?', a: 'Yes, children of any age are welcome. Each hotel studio is for 2 people, with no extra beds, so a family books as many studios as it needs.' },
        ],
        producto: {
          titulo: 'Book in La Ventana',
          texto: 'With La Ventana Travel you book fly fishing by the day, or a package with hotel, transfers and trips out to sea.',
        },
      },
    },
  },

  // 6. Calendario de fauna marina de Baja California Sur ───────────────────────────────────────────────────────
  {
    id: 'calendario-fauna-marina-bcs',
    sede: null,
    actualizado: ACTUALIZADO,
    foto: {
      src: '/photos/puerto-chale/jorobada-saltando.webp',
      alt: { es: 'Una ballena jorobada salta fuera del agua en Baja California Sur', en: 'A humpback whale breaches in Baja California Sur' },
    },
    destinos: [SEDE_CHALE, SEDE_VENTANA, SEDE_LA_PAZ],
    tema: 'mar',
    fotos: [
      { src: '/photos/puerto-chale/ballena-asomada.webp', alt: { es: 'Una ballena gris asoma la cabeza frente a la isla', en: 'A gray whale lifts its head out of the water in front of the island' } },
      { src: '/catalogo/la-ventana-travel-paquete-5-noches.webp', alt: { es: 'Una persona nadando entre un enorme cardumen de rayas', en: 'A person swimming among a huge school of rays' } },
      { src: '/photos/marlin-en-equipo.webp', alt: { es: 'Marlin capturado en equipo, listo para la foto y la liberación', en: 'Marlin landed as a team, ready for the photo and release' } },
      { src: '/photos/puerto-chale/jorobada-bajo-el-agua.webp', alt: { es: 'Una ballena jorobada nada bajo el agua con las aletas abiertas', en: 'A humpback whale swims underwater with its fins spread' } },
    ],
    fotoFrase: { src: '/photos/puerto-chale/ballenas-junto-a-la-panga.webp', alt: { es: 'Dos ballenas grises nadan pegadas a la panga mientras una pasajera las toca', en: 'Two gray whales swim right beside the panga while a passenger reaches out to touch them' } },
    textos: {
      es: {
        slug: 'calendario-fauna-marina-baja-california-sur',
        titulo: 'Calendario de fauna marina en Baja California Sur, mes por mes',
        metaTitulo: 'Fauna marina en Baja California Sur: calendario por mes',
        metaDescripcion: 'Cuándo ver ballena gris, orcas, mobulas y ballena jorobada en Baja California Sur, y cuándo pescar dorado y marlín. Calendario mes por mes y desde dónde.',
        respuesta: 'En Baja California Sur siempre hay algo en el mar. De enero a marzo, la ballena gris en Bahía Magdalena. De abril a julio, mobulas y orcas en La Ventana. De junio a octubre, dorado y marlín en La Paz. Y al cierre del año, la ballena jorobada.',
        frase: 'El invierno es de las ballenas y el verano, del marlín.',
        datos: [
          { etiqueta: 'Ene a mar', valor: 'Ballena gris en Bahía Magdalena' },
          { etiqueta: 'Abr a jul', valor: 'Mobulas y orcas en La Ventana' },
          { etiqueta: 'Jun a oct', valor: 'Dorado y marlín en La Paz' },
          { etiqueta: 'Oct a dic', valor: 'Ballena jorobada y safari marino' },
        ],
        calendario: {
          titulo: 'Qué se ve y qué se pesca cada mes',
          filas: [
            { nombre: 'Ballena gris · Puerto Chale', meses: [1, 2, 3], fuertes: [1, 2, 3] },
            { nombre: 'Orcas · La Ventana', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Mobulas · La Ventana', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Ballena jorobada · Puerto Chale', meses: [10, 11, 12] },
            { nombre: 'Lobos marinos y delfines', meses: TODO_EL_ANIO },
            { nombre: 'Marlín y dorado · La Paz', meses: [6, 7, 8, 9, 10], fuertes: [6, 7, 8, 9, 10] },
            { nombre: 'Jurel · La Paz', meses: [1, 2, 3, 4] },
          ],
          nota: 'Son animales libres y el mar cambia cada año. Los meses marcados son los de más encuentros.',
        },
        secciones: [
          {
            titulo: 'Invierno: enero a marzo',
            parrafos: [
              'Es la temporada de la ballena gris. Llega del Ártico a Bahía Magdalena a tener a sus crías, y desde Puerto Chale la ves de cerca en recorridos de {duracion:piratas-adventures/avistamiento-ballenas}. En La Paz, el invierno es del jurel.',
            ],
          },
          {
            titulo: 'Primavera: abril a junio',
            parrafos: [
              'Las mobulas se juntan por miles frente a La Ventana y saltan fuera del agua. Detrás llegan las orcas, que se alimentan de ellas. Son los meses con más encuentros en el seafari.',
            ],
          },
          {
            titulo: 'Verano: julio a septiembre',
            parrafos: [
              'El agua se calienta y La Paz entra en su temporada fuerte de pesca: dorado, marlín, atún aleta amarilla y pez vela. En La Ventana siguen las orcas.',
            ],
          },
          {
            titulo: 'Otoño: octubre a diciembre',
            parrafos: [
              'En Puerto Chale sale el safari marino, {duracion:piratas-adventures/safari-marino} entre islas con lobos marinos, y a finales de año pasa la ballena jorobada. En La Paz cierra la temporada de dorado y empieza la de sierra.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuál es la mejor época para ver ballenas en Baja California Sur?', a: 'De enero a marzo, cuando la ballena gris está en Bahía Magdalena con sus crías. A finales de año pasa la ballena jorobada.' },
          { q: '¿Cuándo se ven orcas en Baja California Sur?', a: 'En La Ventana las orcas vienen todo el año. Los meses con más encuentros suelen ser de finales de abril a julio.' },
          { q: '¿Cuándo es la temporada de mobulas?', a: 'De abril a julio, con el momento más fuerte en mayo y junio, frente a La Ventana.' },
          { q: '¿Se puede ver todo en un solo viaje?', a: 'Cada especie tiene su época, así que el mes lo eliges por lo que más quieras ver. Con una semana puedes juntar dos mares: un paquete en La Ventana y un día de pesca en La Paz.' },
        ],
        producto: {
          titulo: 'Elige tu destino',
          texto: 'Cada sede tiene su mar y su temporada. En su página están las salidas, los precios y las fechas libres.',
        },
      },
      en: {
        slug: 'baja-california-sur-marine-life-calendar',
        titulo: 'Baja California Sur marine life calendar, month by month',
        metaTitulo: 'Baja California Sur Marine Life Calendar by Month',
        metaDescripcion: 'When to see gray whales, orcas, mobula rays and humpbacks in Baja California Sur, and when to fish dorado and marlin. Month-by-month calendar and where.',
        respuesta: 'There is always something in the sea in Baja California Sur. January to March: gray whales in Magdalena Bay. April to July: mobula rays and orcas in La Ventana. June to October: dorado and marlin in La Paz. And at year’s end, humpback whales.',
        frase: 'Winter belongs to the whales, summer to the marlin.',
        datos: [
          { etiqueta: 'Jan to Mar', valor: 'Gray whales in Magdalena Bay' },
          { etiqueta: 'Apr to Jul', valor: 'Mobula rays and orcas in La Ventana' },
          { etiqueta: 'Jun to Oct', valor: 'Dorado and marlin in La Paz' },
          { etiqueta: 'Oct to Dec', valor: 'Humpback whales and marine safari' },
        ],
        calendario: {
          titulo: 'What you see and catch each month',
          filas: [
            { nombre: 'Gray whales · Puerto Chale', meses: [1, 2, 3], fuertes: [1, 2, 3] },
            { nombre: 'Orcas · La Ventana', meses: TODO_EL_ANIO, fuertes: [5, 6, 7] },
            { nombre: 'Mobula rays · La Ventana', meses: [4, 5, 6, 7], fuertes: [5, 6], fuente: 'region' },
            { nombre: 'Humpback whales · Puerto Chale', meses: [10, 11, 12] },
            { nombre: 'Sea lions and dolphins', meses: TODO_EL_ANIO },
            { nombre: 'Marlin and dorado · La Paz', meses: [6, 7, 8, 9, 10], fuertes: [6, 7, 8, 9, 10] },
            { nombre: 'Yellowtail · La Paz', meses: [1, 2, 3, 4] },
          ],
          nota: 'These are wild animals and the sea changes every year. The marked months are the ones with the most encounters.',
        },
        secciones: [
          {
            titulo: 'Winter: January to March',
            parrafos: [
              'This is gray whale season. They come from the Arctic to Magdalena Bay to give birth, and from Puerto Chale you see them up close on 2-hour trips. In La Paz, winter belongs to yellowtail.',
            ],
          },
          {
            titulo: 'Spring: April to June',
            parrafos: [
              'Mobula rays gather by the thousands off La Ventana and leap out of the water. Orcas, which feed on them, follow. These are the months with the most encounters on the seafari.',
            ],
          },
          {
            titulo: 'Summer: July to September',
            parrafos: [
              'The water warms up and La Paz hits its peak fishing season: dorado, marlin, yellowfin tuna and sailfish. Orcas are still around La Ventana.',
            ],
          },
          {
            titulo: 'Fall: October to December',
            parrafos: [
              'In Puerto Chale the marine safari runs, {duracion:piratas-adventures/safari-marino} among the islands with sea lions, and humpback whales pass through late in the year. In La Paz, dorado season winds down and sierra season begins.',
            ],
          },
        ],
        faq: [
          { q: 'When is the best time to see whales in Baja California Sur?', a: 'January to March, when gray whales are in Magdalena Bay with their calves. Humpback whales pass through late in the year.' },
          { q: 'When can you see orcas in Baja California Sur?', a: 'Orcas come to La Ventana all year. The months with the most encounters are usually late April through July.' },
          { q: 'When is mobula ray season?', a: 'April to July, peaking in May and June, off La Ventana.' },
          { q: 'Can I see everything in one trip?', a: 'Each species has its season, so you pick your month by what you most want to see. With a week you can fit in two seas: a La Ventana package and a fishing day in La Paz.' },
        ],
        producto: {
          titulo: 'Pick your destination',
          texto: 'Each destination has its own sea and season. Trips, prices and open dates are on its page.',
        },
      },
    },
  },

  // 7. Paquetes vacacionales en Baja California Sur ────────────────────────────────────────────────────────────
  {
    id: 'paquetes-vacacionales-bcs',
    sede: 'la-ventana',
    actualizado: REVISADO,
    foto: {
      src: '/catalogo/la-ventana-travel-hospedaje-la-ventana.webp',
      alt: { es: 'Vista aérea del Hotel Casa Arrecife con el mar de La Ventana al fondo', en: 'Aerial view of Hotel Casa Arrecife with the sea off La Ventana behind it' },
    },
    destinos: PAQUETES_VENTANA,
    tema: 'estancia',
    fotos: [
      { src: '/catalogo/la-ventana-travel-paquete-7-noches.webp', alt: { es: 'Una persona haciendo snorkel entre peces rayados', en: 'A person snorkeling among striped fish' } },
      { src: '/catalogo/la-ventana-travel-avistamiento-ballenas-orcas.webp', alt: { es: 'Dos orcas nadando bajo la superficie del mar', en: 'Two orcas swimming just below the sea surface' } },
      { src: '/catalogo/la-ventana-travel-hospedaje-cocina.webp', alt: { es: 'La cocina compartida del Hotel Casa Arrecife', en: 'The shared kitchen at Hotel Casa Arrecife' } },
      { src: '/catalogo/la-ventana-travel-paquete-5-noches.webp', alt: { es: 'Una persona nadando entre un enorme cardumen de rayas', en: 'A person swimming among a huge school of rays' } },
      { src: '/photos/flota-pangas-bahia.webp', alt: { es: 'Las siete pangas de Sal y Sol formadas en el agua turquesa de la bahía', en: 'The seven Sal y Sol pangas lined up on the turquoise water of the bay' } },
    ],
    fotoFrase: { src: '/catalogo/la-ventana-travel-hospedaje-fogata.webp', alt: { es: 'La fogata azul del patio del Hotel Casa Arrecife al atardecer', en: 'The blue fire pit in the Hotel Casa Arrecife courtyard at dusk' } },
    textos: {
      es: {
        slug: 'paquetes-vacacionales-baja-california-sur',
        titulo: 'Paquetes en La Ventana: hotel, traslado y salidas al mar con orcas',
        metaTitulo: 'Paquetes en La Ventana, BCS: hotel y salidas al mar con orcas',
        metaDescripcion: 'Paquetes de 5 y 7 noches en La Ventana, Baja California Sur: hotel, traslado del aeropuerto y de 4 a 6 salidas al mar para buscar orcas y fauna marina.',
        respuesta: 'En La Ventana, Baja California Sur, hay dos paquetes: de 5 y de 7 noches. Los dos traen el Hotel Casa Arrecife, el traslado redondo del aeropuerto y las salidas al mar de seafari: 4 en el de 5 noches y 6 en el de 7. El precio es por persona.',
        frase: 'Te recogen en el aeropuerto y al día siguiente ya estás en el mar.',
        datos: [
          { etiqueta: 'Paquetes', valor: '5 noches y 7 noches' },
          { etiqueta: 'Salidas al mar', valor: '4 o 6 seafaris' },
          { etiqueta: 'Hospedaje', valor: 'Hotel Casa Arrecife' },
          { etiqueta: 'Traslado', valor: 'Aeropuerto, ida y vuelta' },
        ],
        secciones: [
          {
            titulo: '¿Qué incluye cada paquete?',
            parrafos: ['Los dos traen lo mismo. Cambia el número de noches y de salidas:'],
            lista: [
              'Hospedaje en el Hotel Casa Arrecife, en estudio para 2 personas con cama king size',
              'Traslado del aeropuerto al llegar y de regreso al terminar',
              'Seafari de 5 a 6 horas cada día de mar: orcas, delfines, lobos marinos y snorkel',
              'Comida ligera, botanas, bebidas y equipo de snorkel a bordo',
            ],
          },
          {
            titulo: '¿Cómo son los días?',
            parrafos: [
              'El día 1 es de llegada: te recogen en el aeropuerto y te llevan al hotel. Desde el día 2 sales cada mañana al mar, entre las 7:00 y las 8:00 am, y vuelves pasado el mediodía con la tarde libre. El último día te llevan de vuelta al aeropuerto.',
            ],
          },
          {
            titulo: '¿Qué va por tu cuenta?',
            parrafos: [
              'Los vuelos y las comidas en tierra. Para comer hay restaurantes a menos de 1 km del hotel, y el hotel tiene cocina compartida por si prefieres cocinar.',
            ],
          },
          {
            titulo: '¿5 o 7 noches?',
            parrafos: [
              'Cada salida es una oportunidad más de encontrar orcas. Con 7 noches tienes 6 salidas en lugar de 4, y más margen: si un día el mar no deja salir, esa salida se repone otro día de tu estancia.',
            ],
          },
          {
            titulo: '¿Y en La Paz o Puerto Chale?',
            parrafos: [
              'Ahí se reserva por día: la pesca deportiva en panga privada en La Paz y el avistamiento de ballena gris en Puerto Chale. Puedes sumar uno de esos días a tu viaje, antes o después del paquete.',
            ],
          },
        ],
        faq: [
          { q: '¿Qué paquetes vacacionales hay en Baja California Sur?', a: 'En Sun Baja Experience hay dos, los dos en La Ventana con La Ventana Travel: de 5 noches con 4 salidas al mar y de 7 noches con 6. Incluyen hotel y traslado del aeropuerto.' },
          { q: '¿El precio es por persona o por habitación?', a: 'Por persona. Cada estudio del hotel es para 2 personas.' },
          { q: '¿Puedo viajar con niños?', a: 'Sí, niños de cualquier edad son bienvenidos. Cada estudio es para 2 personas, sin camas extra ni cunas, así que una familia reserva los estudios que necesite.' },
          { q: '¿Puedo cambiar la fecha?', a: 'Sí. Los paquetes con hotel se pueden cambiar hasta 30 días antes de tu llegada.' },
          { q: '¿Cuál es la mejor época para el paquete?', a: 'Las orcas vienen todo el año. De finales de abril a julio llegan las mobulas y suele haber más encuentros.' },
        ],
        producto: {
          titulo: 'Los dos paquetes',
          texto: 'El precio por persona, las fechas libres y el día por día están en la página de cada paquete.',
        },
      },
      en: {
        slug: 'baja-california-sur-vacation-packages',
        titulo: 'La Ventana packages: hotel, transfers and orca trips out to sea',
        metaTitulo: 'La Ventana Packages: Hotel, Transfers & Orca Trips at Sea',
        metaDescripcion: '5- and 7-night packages in La Ventana, Baja, priced per person: hotel, airport transfers and 4 to 6 trips out to sea to find orcas and marine life.',
        respuesta: 'La Ventana, Baja California Sur, has two packages: 5 nights and 7 nights. Both come with Hotel Casa Arrecife, round-trip airport transfers and seafari trips out to sea: 4 on the 5-night package and 6 on the 7-night one. Prices are per person.',
        frase: 'You are picked up at the airport, and the next morning you are at sea.',
        datos: [
          { etiqueta: 'Packages', valor: '5 nights and 7 nights' },
          { etiqueta: 'Trips to sea', valor: '4 or 6 seafaris' },
          { etiqueta: 'Lodging', valor: 'Hotel Casa Arrecife' },
          { etiqueta: 'Transfers', valor: 'Airport, round trip' },
        ],
        secciones: [
          {
            titulo: 'What does each package include?',
            parrafos: ['Both come with the same things. The number of nights and trips changes:'],
            lista: [
              'Lodging at Hotel Casa Arrecife, in a studio for 2 with a king-size bed',
              'Airport pickup when you arrive and a ride back at the end',
              'A 5- to 6-hour seafari on each sea day: orcas, dolphins, sea lions and snorkeling',
              'A light meal, snacks, drinks and snorkeling gear on board',
            ],
          },
          {
            titulo: 'What are the days like?',
            parrafos: [
              'Day 1 is arrival day: you are picked up at the airport and driven to the hotel. From day 2 you head out to sea each morning, between 7:00 and 8:00 am, and are back in the early afternoon with the rest of the day free. On the last day you are driven back to the airport.',
            ],
          },
          {
            titulo: 'What do I cover myself?',
            parrafos: [
              'Flights and meals on land. For meals there are restaurants less than 1 km from the hotel, and the hotel has a shared kitchen if you would rather cook.',
            ],
          },
          {
            titulo: '5 nights or 7?',
            parrafos: [
              'Every trip is one more chance of finding orcas. With 7 nights you get 6 trips instead of 4, and more room: if the sea keeps the boat in one day, that trip is made up on another day of your stay.',
            ],
          },
          {
            titulo: 'What about La Paz or Puerto Chale?',
            parrafos: [
              'Those are booked by the day: private panga sportfishing in La Paz and gray whale watching in Puerto Chale. You can add one of those days to your trip, before or after the package.',
            ],
          },
        ],
        faq: [
          { q: 'What vacation packages are available for Baja California Sur?', a: 'Sun Baja Experience has two, both in La Ventana with La Ventana Travel: 5 nights with 4 trips out to sea, and 7 nights with 6. They include the hotel and airport transfers.' },
          { q: 'Is the price per person or per room?', a: 'Per person. Each hotel studio is for 2 people.' },
          { q: 'Can I travel with children?', a: 'Yes, children of any age are welcome. Each studio is for 2 people, with no extra beds or cribs, so a family books as many studios as it needs.' },
          { q: 'Can I change my dates?', a: 'Yes. Packages with hotel can be changed up to 30 days before arrival.' },
          { q: 'When is the best time for the package?', a: 'Orcas come all year. From late April to July the mobula rays arrive and there are usually more encounters.' },
        ],
        producto: {
          titulo: 'The two packages',
          texto: 'Per-person prices, open dates and the day-by-day plan are on each package’s page.',
        },
      },
    },
  },

  // 8. Pesca en panga en La Paz ────────────────────────────────────────────────────────────────────────────────
  {
    id: 'pesca-en-panga-la-paz',
    sede: 'la-paz',
    actualizado: REVISADO,
    foto: {
      src: '/photos/flota-pangas-bahia.webp',
      alt: { es: 'Las siete pangas de Sal y Sol formadas en el agua turquesa de la bahía de La Paz', en: 'The seven Sal y Sol pangas lined up on the turquoise water of La Paz bay' },
    },
    destinos: [PESCA_LA_PAZ, SEDE_LA_PAZ],
    tema: 'mar',
    fotos: [
      { src: '/photos/panga-acantilados-rojos.webp', alt: { es: 'La panga Volador III cruza el agua clara frente a acantilados rojos', en: 'The panga Volador III crosses clear water in front of red cliffs' } },
      { src: '/photos/yellowtail-pelicanos-bahia.webp', alt: { es: 'De regreso a la bahía, con pelícanos alrededor', en: 'Heading back into the bay, pelicans alongside' } },
      { src: '/photos/dorado-bajo-toldo.webp', alt: { es: 'Dorado recién subido, a la sombra del toldo', en: 'Mahi just brought aboard, in the shade of the canopy' } },
      { src: '/photos/grupo-cabrilla-costa.webp', alt: { es: 'Familia con su captura, cerca de la costa', en: 'Family with their catch, close to shore' } },
      { src: '/photos/pareja-dorados.webp', alt: { es: 'Dos amigos con su dorado', en: 'Two friends with their mahi' } },
    ],
    fotoFrase: { src: '/photos/panga-rumbo-a-la-pesca.webp', alt: { es: 'La panga Storm, con toldo verde, navega a toda velocidad con tres pescadores a bordo', en: 'The panga Storm, with its green canopy, speeds across the water with three anglers on board' } },
    textos: {
      es: {
        slug: 'pesca-en-panga-la-paz',
        titulo: 'Pesca en panga en La Paz: qué es y cómo es un día a bordo',
        metaTitulo: 'Pesca en panga en La Paz: qué es y cómo es un día a bordo',
        metaDescripcion: 'Qué es una panga y cómo es un día de pesca en La Paz con un capitán local: {duracion:sal-y-sol/pesca-deportiva}, solo tu grupo a bordo, qué incluye y qué llevar.',
        respuesta: 'La panga es la lancha abierta, con motor fuera de borda, en la que trabajan los pescadores de Baja California Sur. En La Paz pescas en panga privada: van solo tu grupo y un capitán local, {duracion:sal-y-sol/pesca-deportiva}, saliendo al amanecer de {salida:sal-y-sol/pesca-deportiva}.',
        frase: 'A bordo van solo tu grupo y tu capitán.',
        datos: [
          { etiqueta: 'A bordo', valor: 'Solo tu grupo, hasta {maximo:sal-y-sol/pesca-deportiva} personas' },
          { etiqueta: 'Duración', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'Sale de', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
          { etiqueta: 'Incluye', valor: 'Capitán, comida y bebidas' },
        ],
        secciones: [
          {
            titulo: '¿Qué es una panga?',
            parrafos: [
              'Es una lancha de fibra de vidrio, abierta, ligera y rápida. Es la embarcación de trabajo de los pescadores del Mar de Cortés desde hace generaciones, y por eso los capitanes la conocen de memoria.',
              'Las de Sal y Sol llevan toldo para la sombra, y en el muelle se les conoce por su nombre: Don Piry, Volador, Dream, Escoria del Mar, Esperanzas, Storm y Volador III.',
            ],
          },
          {
            titulo: '¿Cómo es un día de pesca?',
            parrafos: [
              'Tu capitán te espera al amanecer en el muelle de {salida:sal-y-sol/pesca-deportiva} con la panga lista. Él elige el rumbo según cómo amaneció el mar.',
              'Pasas {duracion:sal-y-sol/pesca-deportiva} en el Mar de Cortés buscando lo que da la temporada. Regresas al muelle con la captura y las fotos, con los pelícanos rondando la panga.',
            ],
          },
          {
            titulo: '¿Qué incluye?',
            parrafos: ['La salida trae lo necesario para que tú solo te ocupes de pescar:'],
            lista: [
              'Panga privada para tu grupo, con capitán local',
              'Desayuno ligero y comida a bordo',
              'Aperitivos y bebidas',
              'Hielera con hielo para la captura',
            ],
          },
          {
            titulo: '¿Qué llevar?',
            parrafos: ['Poco, pero ayuda:'],
            lista: [
              'Una chamarra ligera o rompevientos para la brisa del amanecer',
              'Pastillas para el mareo, si eres sensible al movimiento: se toman antes de zarpar',
              'Una hielera para llevarte tus filetes al terminar',
              'Bloqueador, gorra y lentes de sol',
            ],
          },
          {
            titulo: '¿Cuántos caben y cómo se paga?',
            parrafos: [
              'Hay pangas para hasta 3 y para hasta {maximo:sal-y-sol/pesca-deportiva} personas, y pueden ir niños de cualquier edad. El precio base cubre a {personas:sal-y-sol/pesca-deportiva} personas; cada persona más tiene un cargo que ves antes de pagar.',
              'Puedes pagar todo en línea o apartar tu fecha con el {anticipo:sal-y-sol/pesca-deportiva} y pagar el resto en efectivo, en pesos o en dólares. La licencia de pesca va aparte, solo para quien pesca.',
            ],
          },
        ],
        faq: [
          { q: '¿Cuánto cuesta rentar una panga de pesca en La Paz?', a: 'La panga privada con capitán cuesta {precio:sal-y-sol/pesca-deportiva} con IVA incluido, para {personas:sal-y-sol/pesca-deportiva} personas. Cada persona más paga {extra:sal-y-sol/pesca-deportiva}, hasta {maximo:sal-y-sol/pesca-deportiva}. Reservas en línea con tarjeta y puedes apartar con el {anticipo:sal-y-sol/pesca-deportiva}.' },
          { q: '¿Qué es una panga?', a: 'Una lancha abierta de fibra de vidrio con motor fuera de borda, ligera y rápida. Es la embarcación tradicional de los pescadores de Baja California Sur.' },
          { q: '¿La panga es privada o compartida?', a: 'Privada. A bordo van solo tu grupo y tu capitán.' },
          { q: '¿Se pescan marlín y dorado desde una panga?', a: 'Sí. De junio a octubre es la temporada de marlín y dorado en La Paz, y se pescan desde la panga.' },
          { q: '¿Pueden ir niños o gente que nunca ha pescado?', a: 'Sí. Pueden ir niños de cualquier edad, y el capitán te explica todo a bordo.' },
          { q: '¿Qué pasa si hay mal clima?', a: 'Eliges tú: cambias la fecha o recibes el reembolso completo. Aplica cuando la capitanía de puerto o tu capitán deciden que el mar no está para salir.' },
        ],
        producto: {
          titulo: 'Reserva tu panga',
          texto: 'Sal y Sol Sportfishing sale todos los días del año. El precio y las fechas libres están en su página.',
        },
      },
      en: {
        slug: 'panga-fishing-la-paz',
        titulo: 'Panga fishing in La Paz: what it is and what a day on board is like',
        metaTitulo: 'Panga Fishing in La Paz: What It Is & a Day on Board',
        metaDescripcion: 'What a panga is and what a fishing day in La Paz with a local captain is like: {duracion:sal-y-sol/pesca-deportiva}, only your group on board, what is included and what to bring.',
        respuesta: 'A panga is the open, outboard-powered skiff that the fishermen of Baja California Sur work from. In La Paz you fish on a private panga: just your group and a local captain, for {duracion:sal-y-sol/pesca-deportiva}, leaving {salida:sal-y-sol/pesca-deportiva} at dawn.',
        frase: 'On board it is just your group and your captain.',
        datos: [
          { etiqueta: 'On board', valor: 'Just your group, up to {maximo:sal-y-sol/pesca-deportiva} people' },
          { etiqueta: 'Length', valor: '{duracion:sal-y-sol/pesca-deportiva}' },
          { etiqueta: 'Leaves from', valor: '{salida:sal-y-sol/pesca-deportiva}, La Paz' },
          { etiqueta: 'Includes', valor: 'Captain, food and drinks' },
        ],
        secciones: [
          {
            titulo: 'What is a panga?',
            parrafos: [
              'It is an open fiberglass skiff, light and fast. It has been the working boat of Sea of Cortez fishermen for generations, which is why the captains know it inside out.',
              'Sal y Sol’s pangas have a canopy for shade, and on the dock everyone knows them by name: Don Piry, Volador, Dream, Escoria del Mar, Esperanzas, Storm and Volador III.',
            ],
          },
          {
            titulo: 'What is a fishing day like?',
            parrafos: [
              'Your captain is waiting at dawn on the {salida:sal-y-sol/pesca-deportiva} dock with the panga ready. He picks the heading based on how the sea looks that morning.',
              'You spend {duracion:sal-y-sol/pesca-deportiva} on the Sea of Cortez going after whatever the season brings. You come back to the dock with the catch and the photos, pelicans circling the panga.',
            ],
          },
          {
            titulo: 'What is included?',
            parrafos: ['The trip comes with what you need so all you have to do is fish:'],
            lista: [
              'A private panga for your group, with a local captain',
              'A light breakfast and lunch on board',
              'Snacks and drinks',
              'A cooler with ice for the catch',
            ],
          },
          {
            titulo: 'What should I bring?',
            parrafos: ['Not much, but it helps:'],
            lista: [
              'A light jacket or windbreaker for the dawn breeze',
              'Motion sickness tablets if you are sensitive: take them before leaving the dock',
              'A cooler to take your fillets home',
              'Sunscreen, a cap and sunglasses',
            ],
          },
          {
            titulo: 'How many fit, and how do I pay?',
            parrafos: [
              'There are pangas for up to 3 and for up to {maximo:sal-y-sol/pesca-deportiva} people, and children of any age can come. The base price covers {personas:sal-y-sol/pesca-deportiva} people; each additional person has a charge that you see before you pay.',
              'You can pay in full online, or hold your date with {anticipo:sal-y-sol/pesca-deportiva} and pay the rest in cash, in pesos or dollars. Fishing licenses are separate, only for those who fish.',
            ],
          },
        ],
        faq: [
          { q: 'How much does a panga fishing charter in La Paz cost?', a: 'The private panga with a captain costs {precio:sal-y-sol/pesca-deportiva}, tax included, for {personas:sal-y-sol/pesca-deportiva} people. Each additional person pays {extra:sal-y-sol/pesca-deportiva}, up to {maximo:sal-y-sol/pesca-deportiva}. You book online by card and can hold your date with {anticipo:sal-y-sol/pesca-deportiva}.' },
          { q: 'What is a panga?', a: 'An open fiberglass skiff with an outboard motor, light and fast. It is the traditional boat of the fishermen of Baja California Sur.' },
          { q: 'Is the panga private or shared?', a: 'Private. Only your group and your captain are on board.' },
          { q: 'Can you catch marlin and dorado from a panga?', a: 'Yes. June to October is marlin and dorado season in La Paz, and they are caught from the panga.' },
          { q: 'Can children or first-timers come?', a: 'Yes. Children of any age can come, and the captain walks you through everything on board.' },
          { q: 'What happens in bad weather?', a: 'Your call: a new date or a full refund. That applies whenever the port captain or your captain decides the sea is not fit to go out.' },
        ],
        producto: {
          titulo: 'Book your panga',
          texto: 'Sal y Sol Sportfishing goes out every day of the year. Prices and open dates are on its page.',
        },
      },
    },
  },
  // 9 a 15. Las que salieron del estudio de competencia (2026-11-16), en su propio archivo.
  ...GUIAS_ESTUDIO,
];

/** La guía con ese slug en ese idioma. */
export function getGuia(slug: string, idioma: IdiomaGuia): Guia | undefined {
  return GUIAS.find((guia) => guia.textos[idioma].slug === slug);
}

/**
 * Si el slug es de la guía en el OTRO idioma (el selector de idioma solo cambia `/es` por `/en`), el slug que le
 * toca en este: la página redirige a él en vez de dar 404.
 */
export function slugEnIdioma(slug: string, idioma: IdiomaGuia): string | undefined {
  const otro: IdiomaGuia = idioma === 'es' ? 'en' : 'es';
  return GUIAS.find((guia) => guia.textos[otro].slug === slug)?.textos[idioma].slug;
}

/**
 * Hasta `maximo` guías para el cierre de otra: primero las de su misma sede, luego las de toda la región y al final
 * las demás, en el orden del archivo.
 */
export function guiasRelacionadas(guia: Guia, maximo: number = 3): Guia[] {
  const otras = GUIAS.filter((otra) => otra.id !== guia.id);
  const peso = (otra: Guia) => (otra.sede === guia.sede ? 0 : otra.sede === null || guia.sede === null ? 1 : 2);
  return [...otras].sort((a, b) => peso(a) - peso(b)).slice(0, maximo);
}

/** Las guías de una sede, en el orden del archivo. */
export function guiasDeSede(sede: string): Guia[] {
  return GUIAS.filter((guia) => guia.sede === sede);
}

const CORTES_DE_TITULO = [': ', ', ', ' desde ', ' from '];

/**
 * El título en dos partes para el arranque sobre la foto: lo que nombra el tema, en letra grande, y el resto debajo,
 * más chico (los titulares van en mayúsculas y un título entero no cabe en dos líneas). Corta en el primer separador
 * que aparezca; si no hay ninguno, todo es la parte grande.
 */
export function partesDeTitulo(titulo: string): { principal: string; resto: string | null } {
  const cortes = CORTES_DE_TITULO.map((corte) => ({ corte, en: titulo.indexOf(corte) })).filter((c) => c.en > 0);
  if (cortes.length === 0) return { principal: titulo, resto: null };
  const primero = cortes.reduce((a, b) => (b.en < a.en ? b : a));
  // La preposición se queda con el resto («desde La Paz y Los Cabos»); los dos puntos y la coma se van.
  const resto = titulo.slice(primero.en + primero.corte.length);
  const conPreposicion = primero.corte.trim().length > 1 ? `${primero.corte.trim()} ${resto}` : resto;
  return { principal: titulo.slice(0, primero.en), resto: conPreposicion.charAt(0).toUpperCase() + conPreposicion.slice(1) };
}
