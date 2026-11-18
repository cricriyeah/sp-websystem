// frontend/src/content/faq-servicios.ts
import 'server-only';
import type { Locale } from '@/app/[lang]/dictionaries';

export type PreguntaServicio = { q: string; a: string };

/**
 * Preguntas frecuentes de cada servicio, bilingües. Cada respuesta sale de datos reales del sitio (la ficha del
 * servicio, las reglas de pago y cancelación y el calendario de la sede): no se promete nada que el catálogo no
 * diga. Si un dato cambia en el backoffice (qué incluye, duración, punto de salida, capacidad), se cambia aquí
 * también. La clave es `<empresa>/<servicio>`, la misma de la ruta.
 *
 * `server-only`: si un componente cliente lo importa por error, el build falla.
 */
export const FAQ_SERVICIOS: Record<string, Record<Locale, PreguntaServicio[]>> = {
  'sal-y-sol/pesca-deportiva': {
    es: [
      {
        q: '¿Cuánto cuesta un tour de pesca en La Paz?',
        a: 'La panga privada cuesta {precio:sal-y-sol/pesca-deportiva} con IVA incluido, y ese precio cubre a {personas:sal-y-sol/pesca-deportiva} personas. Cada persona más paga {extra:sal-y-sol/pesca-deportiva}, hasta {maximo:sal-y-sol/pesca-deportiva} por panga. Van incluidos el capitán, el desayuno ligero, la comida, los aperitivos y las bebidas. La licencia de pesca se paga aparte.',
      },
      {
        q: '¿Qué incluye la pesca deportiva?',
        a: 'Una panga privada para tu grupo con un capitán local, desayuno ligero y comida a bordo, aperitivos (fruta y frituras) y bebidas. La licencia de pesca no está incluida: se tramita aparte y solo la necesitan quienes van a pescar.',
      },
      {
        q: '¿A qué hora salimos, de dónde y cuánto dura?',
        a: 'Salimos de {salida:sal-y-sol/pesca-deportiva}, en La Paz. Tú eliges la hora de salida entre las {desde} y las {hasta} al reservar, y la jornada dura {duracion:sal-y-sol/pesca-deportiva}.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'Hasta {maximo:sal-y-sol/pesca-deportiva} personas por panga, y la panga es solo para tu grupo. El precio cubre a {personas:sal-y-sol/pesca-deportiva} personas y cada persona más tiene un cargo, que ves al elegir tu grupo.',
      },
      {
        q: '¿Qué se pesca según la temporada?',
        a: 'De enero a abril, jurel (y también pargo y cabrilla). De junio a octubre, la temporada fuerte: marlín y dorado. En noviembre y diciembre, sierra (y también cochito). Antes de reservar puedes ver el calendario mes por mes en la página de La Paz.',
      },
      {
        q: '¿Necesito licencia de pesca?',
        a: 'Sí: cada persona que pesca a bordo necesita su licencia individual. Puedes agregar el trámite a tu reserva y la gestionamos por ti.',
      },
      {
        q: '¿Puedo pagar con tarjeta? ¿Cuánto es el anticipo?',
        a: 'Sí. Pagas en línea con tarjeta de crédito o débito, en pesos o en dólares, y el total con IVA lo ves antes de pagar. Puedes pagar el 100 % o apartar tu fecha con un anticipo del {anticipo:sal-y-sol/pesca-deportiva} y pagar el resto en efectivo.',
      },
      {
        q: '¿Qué pasa si hay mal clima? ¿Me devuelven mi dinero?',
        a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa. Y puedes cambiar la fecha sin costo hasta 48 horas antes.',
      },
    ],
    en: [
      {
        q: 'How much does a fishing charter in La Paz cost?',
        a: 'The private panga costs {precio:sal-y-sol/pesca-deportiva}, tax included, and that price covers {personas:sal-y-sol/pesca-deportiva} people. Each additional person pays {extra:sal-y-sol/pesca-deportiva}, up to {maximo:sal-y-sol/pesca-deportiva} per panga. The captain, a light breakfast, lunch, snacks and drinks are included. The fishing license is paid separately.',
      },
      {
        q: 'What does the sportfishing trip include?',
        a: 'A private panga for your group with a local captain, a light breakfast and lunch on board, snacks (fruit and chips) and drinks. The fishing license is not included: it is arranged separately, and only the people who will fish need one.',
      },
      {
        q: 'What time do we leave, from where, and how long is it?',
        a: 'We leave from {salida:sal-y-sol/pesca-deportiva} in La Paz. You choose your departure time between {desde} and {hasta} when you book, and the trip lasts {duracion:sal-y-sol/pesca-deportiva}.',
      },
      {
        q: 'How many people can come?',
        a: 'Up to {maximo:sal-y-sol/pesca-deportiva} people per panga, and the panga is only for your group. The price covers {personas:sal-y-sol/pesca-deportiva} people, and each additional person has a charge that you see when you choose your group size.',
      },
      {
        q: 'What do you catch in each season?',
        a: 'January to April: yellowtail (plus snapper and cabrilla). June to October is the peak season: marlin and dorado. In November and December: sierra (plus cochito). You can see the month-by-month calendar on the La Paz page before you book.',
      },
      {
        q: 'Do I need a fishing license?',
        a: 'Yes: each person fishing on board needs an individual license. You can add the paperwork to your booking and we take care of it for you.',
      },
      {
        q: 'Can I pay by card? How much is the deposit?',
        a: 'Yes. You pay online by credit or debit card, in pesos or dollars, and you see the total with tax before you pay. You can pay 100% or hold your date with a {anticipo:sal-y-sol/pesca-deportiva} deposit and pay the rest in cash.',
      },
      {
        q: 'What happens in bad weather? Do I get a refund?',
        a: 'If bad weather keeps the boat in, you choose: another date or a full refund. And you can change your date at no cost up to 48 hours before.',
      },
    ],
  },
  'la-ventana-travel/avistamiento-ballenas-orcas': {
    es: [
      {
        q: '¿Qué incluye el seafari?',
        a: 'Algo de comer, aguas y refrescos, equipo para snorkelear y un rato de snorkel en un arrecife. Si aparecen orcas y el mar lo permite, puedes meterte al agua con ellas. A las ballenas se les mira desde la lancha.',
      },
      {
        q: '¿Qué animales voy a ver? ¿Aseguran que veré orcas?',
        a: 'Las orcas visitan la zona todo el año. Desde abril también llegan ballenas jorobadas y mobulas, y a veces aparecen calderones, cachalotes o mantarrayas gigantes. Los delfines y lobos marinos son comunes. No podemos asegurar qué verás: son animales libres y depende del mar. Lo que sí ocurre en cada salida es que vamos a buscarlos, con quien conoce estas aguas.',
      },
      {
        q: '¿A qué hora sale, de dónde y cuánto dura?',
        a: 'Sale todos los días {horario:la-ventana-travel/avistamiento-ballenas-orcas}, desde {salida:la-ventana-travel/avistamiento-ballenas-orcas}, y dura {duracion:la-ventana-travel/avistamiento-ballenas-orcas}.',
      },
      {
        q: '¿La lancha es compartida o puedo ir con mi grupo solo?',
        a: 'Reservando aquí vas en lancha compartida y pagas por persona, hasta {maximo:la-ventana-travel/avistamiento-ballenas-orcas} personas por reserva. Si quieres una lancha privada para tu grupo, de hasta 10 personas, cuesta $20,000 MXN: pídela por WhatsApp y te ayudamos.',
      },
      {
        q: '¿Puedo combinarlo con hospedaje y traslado?',
        a: 'Sí. Los paquetes de 5 y de 7 noches incluyen hospedaje en el Hotel Casa Arrecife, traslado redondo del aeropuerto y este seafari todos los días de mar.',
      },
      {
        q: '¿Puedo pagar con tarjeta? ¿Cuánto es el anticipo?',
        a: 'Sí. Pagas en línea con tarjeta de crédito o débito, en pesos o en dólares, y el total con IVA lo ves antes de pagar. Puedes pagar el 100 % o apartar tu fecha con un anticipo del {anticipo:la-ventana-travel/avistamiento-ballenas-orcas} y pagar el resto en efectivo.',
      },
      {
        q: '¿Qué pasa si hay mal clima? ¿Me devuelven mi dinero?',
        a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa. Y puedes cambiar la fecha sin costo hasta 48 horas antes.',
      },
    ],
    en: [
      {
        q: 'What does the seafari include?',
        a: 'Some food, water and soft drinks, snorkeling gear and a snorkel stop at a reef. If orcas show up and the sea allows it, you can get in the water with them. Whales are watched from the boat.',
      },
      {
        q: 'What will I see? Do you guarantee orcas?',
        a: 'Orcas visit the area all year round. From April, humpback whales and mobula rays arrive too, and now and then we see pilot whales, sperm whales or giant manta rays. Dolphins and sea lions are common. We cannot promise what you will see: they are wild animals and it depends on the sea. What does happen on every trip is that we go looking for them, with people who know these waters.',
      },
      {
        q: 'What time does it leave, from where, and how long is it?',
        a: 'It leaves every day {horario:la-ventana-travel/avistamiento-ballenas-orcas} from {salida:la-ventana-travel/avistamiento-ballenas-orcas}, and lasts {duracion:la-ventana-travel/avistamiento-ballenas-orcas}.',
      },
      {
        q: 'Is the boat shared, or can I go with just my group?',
        a: 'When you book here you join a shared boat and pay per person, up to {maximo:la-ventana-travel/avistamiento-ballenas-orcas} people per booking. If you want a private boat for your group, up to 10 people, it costs $20,000 MXN: ask for it on WhatsApp and we will help.',
      },
      {
        q: 'Can I combine it with lodging and transfers?',
        a: 'Yes. The 5-night and 7-night packages include lodging at Hotel Casa Arrecife, a round-trip airport transfer and this seafari on every sea day.',
      },
      {
        q: 'Can I pay by card? How much is the deposit?',
        a: 'Yes. You pay online by credit or debit card, in pesos or dollars, and you see the total with tax before you pay. You can pay 100% or hold your date with a {anticipo:la-ventana-travel/avistamiento-ballenas-orcas} deposit and pay the rest in cash.',
      },
      {
        q: 'What happens in bad weather? Do I get a refund?',
        a: 'If bad weather keeps the boat in, you choose: another date or a full refund. And you can change your date at no cost up to 48 hours before.',
      },
    ],
  },
  'la-ventana-travel/pesca-con-mosca': {
    es: [
      {
        q: '¿Cuánto cuesta la pesca con mosca en La Ventana?',
        a: 'El día completo cuesta {precio:la-ventana-travel/pesca-con-mosca} con IVA incluido, para un grupo de hasta {maximo:la-ventana-travel/pesca-con-mosca} personas. El precio es el mismo para todo el grupo: se cobra por día y por grupo.',
      },
      {
        q: '¿Qué incluye?',
        a: 'Una panga para tu grupo, hasta {maximo:la-ventana-travel/pesca-con-mosca} personas, comida ligera, aperitivos y bebidas, y equipo de snorkel para cuando quieras meterte al agua.',
      },
      {
        q: '¿La licencia de pesca está incluida?',
        a: 'No. La licencia de pesca es un extra y se paga aparte.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'Hasta {maximo:la-ventana-travel/pesca-con-mosca} personas por reserva, contando a quien pesca.',
      },
      {
        q: '¿Puedo combinarlo con hospedaje en La Ventana?',
        a: 'Sí: en la página de La Ventana ves los paquetes con hospedaje en el Hotel Casa Arrecife y traslado del aeropuerto, y este día de pesca lo reservas aparte, en la fecha que prefieras.',
      },
      {
        q: '¿Puedo pagar con tarjeta? ¿Cuánto es el anticipo?',
        a: 'Sí. Pagas en línea con tarjeta de crédito o débito, en pesos o en dólares, y el total con IVA lo ves antes de pagar. Puedes pagar el 100 % o apartar tu fecha con un anticipo del {anticipo:la-ventana-travel/pesca-con-mosca} y pagar el resto en efectivo.',
      },
      {
        q: '¿Qué pasa si hay mal clima? ¿Me devuelven mi dinero?',
        a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa. Y puedes cambiar la fecha sin costo hasta 48 horas antes.',
      },
    ],
    en: [
      {
        q: 'How much does fly fishing in La Ventana cost?',
        a: 'The full day costs {precio:la-ventana-travel/pesca-con-mosca}, tax included, for a group of up to {maximo:la-ventana-travel/pesca-con-mosca} people. The price is the same for the whole group: it is charged per day and per group.',
      },
      {
        q: 'What is included?',
        a: 'A panga for your group, up to {maximo:la-ventana-travel/pesca-con-mosca} people, a light meal, snacks and drinks, and snorkeling gear for when you want to get in the water.',
      },
      {
        q: 'Is the fishing license included?',
        a: 'No. The fishing license is an extra and is paid separately.',
      },
      {
        q: 'How many people can come?',
        a: 'Up to {maximo:la-ventana-travel/pesca-con-mosca} people per booking, counting the angler.',
      },
      {
        q: 'Can I combine it with lodging in La Ventana?',
        a: 'Yes: on the La Ventana page you can see the packages with lodging at Hotel Casa Arrecife and airport transfers, and you book this fishing day separately, on the date you prefer.',
      },
      {
        q: 'Can I pay by card? How much is the deposit?',
        a: 'Yes. You pay online by credit or debit card, in pesos or dollars, and you see the total with tax before you pay. You can pay 100% or hold your date with a {anticipo:la-ventana-travel/pesca-con-mosca} deposit and pay the rest in cash.',
      },
      {
        q: 'What happens in bad weather? Do I get a refund?',
        a: 'If bad weather keeps the boat in, you choose: another date or a full refund. And you can change your date at no cost up to 48 hours before.',
      },
    ],
  },
  // Puerto Chale (dueño, 2026-11-12): con los datos de la ficha de cada servicio (migración fleet 0057) y lo que dio la
  // familia (temporadas, equipo propio, menores con carta responsiva). Sin horario ni punto de salida: aún no los dan.
  'piratas-adventures/avistamiento-ballenas': {
    es: [
      {
        q: '¿Cuánto cuesta ver ballenas en Puerto Chale?',
        a: 'El avistamiento de {duracion:piratas-adventures/avistamiento-ballenas} cuesta {precio:piratas-adventures/avistamiento-ballenas} con IVA incluido. El precio es por la panga para tu grupo, de 1 a {personas:piratas-adventures/avistamiento-ballenas} personas, y cada persona extra paga {extra:piratas-adventures/avistamiento-ballenas}, hasta {maximo:piratas-adventures/avistamiento-ballenas}.',
      },
      {
        q: '¿Qué incluye el avistamiento?',
        a: 'Una salida en panga para tu grupo con Piratas Adventures, una familia de pescadores de Puerto Chale. A bordo van refrescos, aguas naturales, agua mineral y sueros sin costo, y puedes traer tus propias bebidas y alimentos.',
      },
      {
        q: '¿Cuánto dura?',
        a: '{duracion:piratas-adventures/avistamiento-ballenas} en la bahía. Si quieres más tiempo, hay recorridos de 3 y 4 horas: pídelos por WhatsApp.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'El precio es por grupo y cubre de 1 a {personas:piratas-adventures/avistamiento-ballenas} personas. Caben más, hasta {maximo:piratas-adventures/avistamiento-ballenas} en total, por un cargo por persona que ves antes de pagar.',
      },
      {
        q: '¿Cuándo hay ballenas?',
        a: 'La temporada fuerte es de enero a marzo: cada invierno la ballena gris llega a Bahía Magdalena a tener a sus crías. A finales de año pasa la ballena jorobada.',
      },
      {
        q: '¿Puedo pagar con tarjeta? ¿Cuánto es el anticipo?',
        a: 'Sí. Pagas en línea con tarjeta de crédito o débito, en pesos o en dólares, y el total con IVA lo ves antes de pagar. Puedes pagar el 100 % o apartar tu fecha con un anticipo del {anticipo:piratas-adventures/avistamiento-ballenas} y pagar el resto en efectivo.',
      },
      {
        q: '¿Qué pasa si hay mal clima? ¿Me devuelven mi dinero?',
        a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa. Los plazos para cambiar o cancelar los ves antes de pagar.',
      },
    ],
    en: [
      {
        q: 'How much does whale watching in Puerto Chale cost?',
        a: 'The whale watching trip lasts {duracion:piratas-adventures/avistamiento-ballenas} and costs {precio:piratas-adventures/avistamiento-ballenas}, tax included. The price is for the panga for your group, 1 to {personas:piratas-adventures/avistamiento-ballenas} people, and each extra person pays {extra:piratas-adventures/avistamiento-ballenas}, up to {maximo:piratas-adventures/avistamiento-ballenas}.',
      },
      {
        q: 'What does the whale watching include?',
        a: 'A panga trip for your group with Piratas Adventures, a family of fishermen from Puerto Chale. Sodas, fresh water, mineral water and electrolyte drinks are on board at no cost, and you can bring your own drinks and food.',
      },
      {
        q: 'How long is it?',
        a: '{duracion:piratas-adventures/avistamiento-ballenas} on the bay. If you want more time, there are 3- and 4-hour trips: ask for them on WhatsApp.',
      },
      {
        q: 'How many people can come?',
        a: 'The price is per group and covers 1 to {personas:piratas-adventures/avistamiento-ballenas} people. More can come, up to {maximo:piratas-adventures/avistamiento-ballenas} in total, for a per-person charge you see before you pay.',
      },
      {
        q: 'When are the whales here?',
        a: 'Peak season is January to March: every winter the gray whales come to Magdalena Bay to give birth. Late in the year, humpback whales pass through.',
      },
      {
        q: 'Can I pay by card? How much is the deposit?',
        a: 'Yes. You pay online by credit or debit card, in pesos or dollars, and you see the total with tax before you pay. You can pay 100% or hold your date with a {anticipo:piratas-adventures/avistamiento-ballenas} deposit and pay the rest in cash.',
      },
      {
        q: 'What happens in bad weather? Do I get a refund?',
        a: 'If bad weather keeps the boat in, you choose: another date or a full refund. You see the deadlines to change or cancel before you pay.',
      },
    ],
  },
  'piratas-adventures/safari-marino': {
    es: [
      {
        q: '¿Qué incluye el safari marino?',
        a: '{duracion:piratas-adventures/safari-marino} en el mar con Piratas Adventures. A bordo van refrescos, aguas naturales, agua mineral y sueros sin costo, a veces también cervezas si lo deseas, y comida sencilla sin costo, como sándwiches o burritos. También puedes traer tus propias bebidas y alimentos.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'El precio cubre a un grupo de {personas:piratas-adventures/safari-marino} personas y caben más por un cargo por persona, hasta {maximo:piratas-adventures/safari-marino}. Si son más, se puede sumar otra embarcación avisando con tiempo.',
      },
      {
        q: '¿Cuándo es la temporada?',
        a: 'De octubre a diciembre. Puedes ver qué hay cada mes en la sección de temporadas de la página de Puerto Chale.',
      },
      {
        q: '¿Pueden ir menores de edad?',
        a: 'Sí. Los menores van con una carta responsiva firmada por su madre, padre o tutor.',
      },
      {
        q: '¿Puedo pagar con tarjeta? ¿Cuánto es el anticipo?',
        a: 'Sí. Pagas en línea con tarjeta de crédito o débito, en pesos o en dólares, y el total con IVA lo ves antes de pagar. Puedes pagar el 100 % o apartar tu fecha con un anticipo del {anticipo:piratas-adventures/safari-marino} y pagar el resto en efectivo.',
      },
      {
        q: '¿Qué pasa si hay mal clima? ¿Me devuelven mi dinero?',
        a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa. Los plazos para cambiar o cancelar los ves antes de pagar.',
      },
    ],
    en: [
      {
        q: 'What does the marine safari include?',
        a: '{duracion:piratas-adventures/safari-marino} at sea with Piratas Adventures. Sodas, fresh water, mineral water and electrolyte drinks are on board at no cost, sometimes beer too if you like, and simple food at no cost, such as sandwiches or burritos. You can also bring your own drinks and food.',
      },
      {
        q: 'How many people can come?',
        a: 'The price covers a group of {personas:piratas-adventures/safari-marino} people, and more can come for a per-person charge, up to {maximo:piratas-adventures/safari-marino}. If you are more, another boat can be added with advance notice.',
      },
      {
        q: 'When is the season?',
        a: 'October to December. You can see what is on each month in the seasons section of the Puerto Chale page.',
      },
      {
        q: 'Can minors come?',
        a: 'Yes. Minors come with a liability waiver signed by their mother, father or guardian.',
      },
      {
        q: 'Can I pay by card? How much is the deposit?',
        a: 'Yes. You pay online by credit or debit card, in pesos or dollars, and you see the total with tax before you pay. You can pay 100% or hold your date with a {anticipo:piratas-adventures/safari-marino} deposit and pay the rest in cash.',
      },
      {
        q: 'What happens in bad weather? Do I get a refund?',
        a: 'If bad weather keeps the boat in, you choose: another date or a full refund. You see the deadlines to change or cancel before you pay.',
      },
    ],
  },
  'piratas-adventures/pesca-deportiva': {
    es: [
      {
        q: '¿Cuánto cuesta la pesca en Puerto Chale?',
        a: 'El día de pesca cuesta {precio:piratas-adventures/pesca-deportiva} con IVA incluido. El precio es por el grupo, hasta {maximo:piratas-adventures/pesca-deportiva} personas, y son {duracion:piratas-adventures/pesca-deportiva} en el Pacífico. La licencia de pesca se paga aparte.',
      },
      {
        q: '¿Qué se pesca en Puerto Chale?',
        a: 'Atún, marlín y pargo. Sales de Puerto Chale, en Bahía Almejas, y pescas {duracion:piratas-adventures/pesca-deportiva} en el Pacífico. Se pesca todo el año: escríbenos por WhatsApp con tus fechas y te decimos qué está saliendo esa semana.',
      },
      {
        q: '¿Qué incluye la pesca deportiva?',
        a: '{duracion:piratas-adventures/pesca-deportiva} de pesca en el Pacífico con Piratas Adventures. A bordo van refrescos, aguas naturales, agua mineral y sueros sin costo y, si quieres, comida sencilla sin costo, como sándwiches o burritos. También puedes traer tus propias bebidas y alimentos. La licencia de pesca no está incluida.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'Hasta {maximo:piratas-adventures/pesca-deportiva} personas, y el precio es por el grupo.',
      },
      {
        q: '¿Tengo que llevar mi equipo?',
        a: 'Casi todos los que vienen traen su propio equipo de pesca. Si no tienes, pregúntanos por WhatsApp antes de reservar.',
      },
      {
        q: '¿Necesito licencia de pesca?',
        a: 'Sí: cada persona que pesca a bordo necesita su licencia individual. Puedes agregar el trámite a tu reserva y la gestionamos por ti.',
      },
      {
        q: '¿Cuándo se puede pescar?',
        a: 'Todo el año.',
      },
      {
        q: '¿Puedo pagar con tarjeta? ¿Cuánto es el anticipo?',
        a: 'Sí. Pagas en línea con tarjeta de crédito o débito, en pesos o en dólares, y el total con IVA lo ves antes de pagar. Puedes pagar el 100 % o apartar tu fecha con un anticipo del {anticipo:piratas-adventures/pesca-deportiva} y pagar el resto en efectivo.',
      },
      {
        q: '¿Qué pasa si hay mal clima? ¿Me devuelven mi dinero?',
        a: 'Si el mal clima impide salir, tú eliges: otra fecha o la devolución completa. Los plazos para cambiar o cancelar los ves antes de pagar.',
      },
    ],
    en: [
      {
        q: 'How much does a fishing trip from Puerto Chale cost?',
        a: 'The fishing day costs {precio:piratas-adventures/pesca-deportiva}, tax included. The price is per group, up to {maximo:piratas-adventures/pesca-deportiva} people, for {duracion:piratas-adventures/pesca-deportiva} on the Pacific. The fishing license is paid separately.',
      },
      {
        q: 'What do you catch from Puerto Chale?',
        a: 'Tuna, marlin and snapper. You leave Puerto Chale, on Bahía Almejas, and fish {duracion:piratas-adventures/pesca-deportiva} on the Pacific. They fish all year: message us on WhatsApp with your dates and we will tell you what is biting that week.',
      },
      {
        q: 'What does the sportfishing trip include?',
        a: '{duracion:piratas-adventures/pesca-deportiva} of fishing on the Pacific with Piratas Adventures. Sodas, fresh water, mineral water and electrolyte drinks are on board at no cost and, if you like, simple food at no cost, such as sandwiches or burritos. You can also bring your own drinks and food. The fishing license is not included.',
      },
      {
        q: 'How many people can come?',
        a: 'Up to {maximo:piratas-adventures/pesca-deportiva} people, and the price is per group.',
      },
      {
        q: 'Do I need to bring my own gear?',
        a: 'Almost everyone who comes brings their own fishing gear. If you do not have any, ask us on WhatsApp before you book.',
      },
      {
        q: 'Do I need a fishing license?',
        a: 'Yes: each person fishing on board needs an individual license. You can add the paperwork to your booking and we take care of it for you.',
      },
      {
        q: 'When can you fish?',
        a: 'All year round.',
      },
      {
        q: 'Can I pay by card? How much is the deposit?',
        a: 'Yes. You pay online by credit or debit card, in pesos or dollars, and you see the total with tax before you pay. You can pay 100% or hold your date with a {anticipo:piratas-adventures/pesca-deportiva} deposit and pay the rest in cash.',
      },
      {
        q: 'What happens in bad weather? Do I get a refund?',
        a: 'If bad weather keeps the boat in, you choose: another date or a full refund. You see the deadlines to change or cancel before you pay.',
      },
    ],
  },
};

/** Las preguntas de un servicio en un idioma, o `null` si ese servicio todavía no las tiene. */
export function getFaqServicio(empresa: string, servicio: string, lang: Locale): PreguntaServicio[] | null {
  return FAQ_SERVICIOS[`${empresa}/${servicio}`]?.[lang] ?? null;
}
