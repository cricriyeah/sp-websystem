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
        q: '¿Qué incluye la pesca deportiva?',
        a: 'Una panga privada para tu grupo con un capitán local, desayuno ligero y comida a bordo, aperitivos (fruta y frituras) y bebidas. La licencia de pesca no está incluida: se tramita aparte y solo la necesitan quienes van a pescar.',
      },
      {
        q: '¿A qué hora salimos, de dónde y cuánto dura?',
        a: 'Salimos de Marina La Costa, en La Paz. Tú eliges la hora de salida entre las {desde} y las {hasta} al reservar, y la jornada dura de 6 a 7 horas.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'Hasta 5 personas por panga, y la panga es solo para tu grupo. El precio base cubre a 2 personas; desde la tercera hay un cargo por persona que ves al elegir tu grupo, antes de pagar.',
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
        q: '¿Cómo pago, y qué pasa si hay mal clima?',
        a: 'Puedes pagar el 100 % en línea o apartar tu fecha con un anticipo del 30 % y pagar el resto en efectivo el día de la salida. Aceptamos pesos y dólares, y el total con IVA lo ves antes de pagar. Si el mal clima impide salir, hay reembolso completo; y puedes cambiar la fecha con al menos 48 horas de anticipación.',
      },
    ],
    en: [
      {
        q: 'What does the sportfishing trip include?',
        a: 'A private panga for your group with a local captain, a light breakfast and lunch on board, snacks (fruit and chips) and drinks. The fishing license is not included: it is arranged separately, and only the people who will fish need one.',
      },
      {
        q: 'What time do we leave, from where, and how long is it?',
        a: 'We leave from Marina La Costa in La Paz. You choose your departure time between {desde} and {hasta} when you book, and the trip lasts 6 to 7 hours.',
      },
      {
        q: 'How many people can come?',
        a: 'Up to 5 people per panga, and the panga is only for your group. The base price covers 2 people; from the third person there is a per-person charge that you see when you choose your group size, before you pay.',
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
        q: 'How do I pay, and what happens in bad weather?',
        a: 'You can pay 100% online, or hold your date with a 30% deposit and pay the rest in cash on the day. We accept pesos and dollars, and you see the total with tax before you pay. If bad weather keeps the boat in, there is a full refund; and you can change your date with at least 48 hours notice.',
      },
    ],
  },
  'la-ventana-travel/avistamiento-ballenas-orcas': {
    es: [
      {
        q: '¿Qué incluye el avistamiento de ballenas y orcas?',
        a: 'Algo de comer, aguas y refrescos, equipo para snorkelear y un rato de snorkel en un arrecife. Si aparecen ballenas u orcas y el mar lo permite, se intenta nadar con ellas.',
      },
      {
        q: '¿Aseguran que veré ballenas u orcas?',
        a: 'No: son animales libres y lo que se ve depende de la temporada y del mar. Lo que sí ocurre en cada salida es que vamos a buscarlas, con quien conoce estas aguas.',
      },
      {
        q: '¿A qué hora sale, de dónde y cuánto dura?',
        a: 'Sale todos los días entre las 7:00 y las 8:00 am, desde La Ventana o Bahía de los Sueños, y dura de 5 a 6 horas.',
      },
      {
        q: '¿La lancha es compartida o puedo ir con mi grupo solo?',
        a: 'Reservando aquí vas en lancha compartida y pagas por persona, hasta 8 personas por reserva. Si quieres una lancha privada para tu grupo, de hasta 10 personas, cuesta $20,000 MXN: pídela por WhatsApp y te ayudamos.',
      },
      {
        q: '¿Puedo combinarlo con hospedaje y traslado?',
        a: 'Sí. Los paquetes de 5 y de 7 noches incluyen hospedaje en el Hotel Casa Arrecife, traslado redondo del aeropuerto y este avistamiento todos los días de mar.',
      },
      {
        q: '¿Cómo pago, y qué pasa si hay mal clima?',
        a: 'Puedes pagar el 100 % en línea o apartar tu fecha con un anticipo del 30 % y pagar el resto en efectivo. Aceptamos pesos y dólares, y el total con IVA lo ves antes de pagar. Si el mal clima impide salir, hay reembolso completo; y puedes cambiar la fecha con al menos 48 horas de anticipación.',
      },
    ],
    en: [
      {
        q: 'What does whale and orca watching include?',
        a: 'Some food, water and soft drinks, snorkeling gear and a snorkel stop at a reef. If whales or orcas show up and the sea allows it, we try to swim with them.',
      },
      {
        q: 'Do you guarantee I will see whales or orcas?',
        a: 'No: they are wild animals, and what you see depends on the season and the sea. What does happen on every trip is that we go looking for them, with people who know these waters.',
      },
      {
        q: 'What time does it leave, from where, and how long is it?',
        a: 'It leaves every day between 7:00 and 8:00 am from La Ventana or Bahía de los Sueños, and lasts 5 to 6 hours.',
      },
      {
        q: 'Is the boat shared, or can I go with just my group?',
        a: 'When you book here you join a shared boat and pay per person, up to 8 people per booking. If you want a private boat for your group, up to 10 people, it costs $20,000 MXN: ask for it on WhatsApp and we will help.',
      },
      {
        q: 'Can I combine it with lodging and transfers?',
        a: 'Yes. The 5-night and 7-night packages include lodging at Hotel Casa Arrecife, a round-trip airport transfer and this whale watching on every sea day.',
      },
      {
        q: 'How do I pay, and what happens in bad weather?',
        a: 'You can pay 100% online, or hold your date with a 30% deposit and pay the rest in cash. We accept pesos and dollars, and you see the total with tax before you pay. If bad weather keeps the boat in, there is a full refund; and you can change your date with at least 48 hours notice.',
      },
    ],
  },
  'la-ventana-travel/pesca-con-mosca': {
    es: [
      {
        q: '¿Cómo funciona el precio de la pesca con mosca?',
        a: 'Es un día completo para ti y hasta dos acompañantes, y el precio es el mismo si van uno, dos o tres: se cobra por día y por grupo, no por persona.',
      },
      {
        q: '¿Qué incluye?',
        a: 'Una panga para ti y hasta dos acompañantes, comida ligera, aperitivos y bebidas, y equipo de snorkel para cuando quieras meterte al agua.',
      },
      {
        q: '¿La licencia de pesca está incluida?',
        a: 'No. La licencia de pesca es un extra y se paga aparte.',
      },
      {
        q: '¿Cuántas personas pueden ir?',
        a: 'Hasta 3 personas por reserva: quien pesca y dos acompañantes.',
      },
      {
        q: '¿Puedo combinarlo con hospedaje en La Ventana?',
        a: 'Sí: en la página de La Ventana ves los paquetes con hospedaje en el Hotel Casa Arrecife y traslado del aeropuerto, y este día de pesca lo reservas aparte, en la fecha que prefieras.',
      },
      {
        q: '¿Cómo pago, y qué pasa si hay mal clima?',
        a: 'Puedes pagar el 100 % en línea o apartar tu fecha con un anticipo del 30 % y pagar el resto en efectivo. Aceptamos pesos y dólares, y el total con IVA lo ves antes de pagar. Si el mal clima impide salir, hay reembolso completo; y puedes cambiar la fecha con al menos 48 horas de anticipación.',
      },
    ],
    en: [
      {
        q: 'How does fly fishing pricing work?',
        a: 'It is a full day for you and up to two companions, and the price is the same whether one, two or three people come: it is charged per day and per group, not per person.',
      },
      {
        q: 'What is included?',
        a: 'A panga for you and up to two companions, a light meal, snacks and drinks, and snorkeling gear for when you want to get in the water.',
      },
      {
        q: 'Is the fishing license included?',
        a: 'No. The fishing license is an extra and is paid separately.',
      },
      {
        q: 'How many people can come?',
        a: 'Up to 3 people per booking: the angler and two companions.',
      },
      {
        q: 'Can I combine it with lodging in La Ventana?',
        a: 'Yes: on the La Ventana page you can see the packages with lodging at Hotel Casa Arrecife and airport transfers, and you book this fishing day separately, on the date you prefer.',
      },
      {
        q: 'How do I pay, and what happens in bad weather?',
        a: 'You can pay 100% online, or hold your date with a 30% deposit and pay the rest in cash. We accept pesos and dollars, and you see the total with tax before you pay. If bad weather keeps the boat in, there is a full refund; and you can change your date with at least 48 hours notice.',
      },
    ],
  },
};

/** Las preguntas de un servicio en un idioma, o `null` si ese servicio todavía no las tiene. */
export function getFaqServicio(empresa: string, servicio: string, lang: Locale): PreguntaServicio[] | null {
  return FAQ_SERVICIOS[`${empresa}/${servicio}`]?.[lang] ?? null;
}
