import 'server-only';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { BloqueDetalle } from '@/components/detalle-producto';

/**
 * Bloques que el detalle de un servicio o paquete pinta después de «Qué incluye» (plan de marketing, puntos 15 y 16):
 * qué se pesca y con qué equipo en la pesca con mosca; el itinerario día por día y la temporada en los paquetes.
 * La clave es la de `imagenes-catalogo.ts` (`servicio:<empresa>/<servicio>` o `paquete:<slug>`).
 *
 * Cada bloque dice cómo se pinta (`detalle-producto.tsx`): `dias` = una fila por día con su ficha de calendario,
 * `filas` = un dato grande con su explicación al lado (qué se ve o se pesca y cuándo), `incluye` = el signo de «Qué
 * incluye» (palomita, guion o pregunta mientras no se confirme).
 *
 * Los itinerarios salen de lo que ya dice la página de La Ventana (seafari del día 2 al 5 o al 7, entrada al hotel
 * de 14:00 a 15:00, salida de 11:00 a 12:00) y la temporada, del dueño (2026-11-11). Lo de la pesca con mosca es de
 * RELLENO hasta que La Ventana Travel confirme especies, meses, equipo y guía: cada dato dice «por confirmar».
 */
// Igual que «Qué se pesca y cuándo»: el animal grande y cuándo al lado (PFD: los dos responden «qué veo y cuándo»).
const TEMPORADA: Record<Locale, BloqueDetalle> = {
  es: {
    tipo: 'filas',
    titulo: 'Temporada',
    items: [
      { valor: 'Orcas', texto: 'Todo el año' },
      { valor: 'Jorobadas y mobulas', texto: 'Desde abril' },
    ],
  },
  en: {
    tipo: 'filas',
    titulo: 'Season',
    items: [
      { valor: 'Orcas', texto: 'Year-round' },
      { valor: 'Humpbacks and mobulas', texto: 'From April' },
    ],
  },
};

function itinerario(lang: Locale, ultimoDiaMar: number): BloqueDetalle {
  const salida = ultimoDiaMar + 1;
  return lang === 'es'
    ? {
      tipo: 'dias',
      titulo: 'Tu viaje, día por día',
      items: [
        { dia: 'Día', numero: '1', titulo: 'Llegada', texto: 'Te recogemos en el aeropuerto y te llevamos al Hotel Casa Arrecife. Entrada de 14:00 a 15:00.' },
        {
          dia: 'Días', numero: `2–${ultimoDiaMar}`, titulo: 'Seafari de orcas y fauna marina',
          texto: 'Sales entre las 7:00 y las 8:00 am, de 5 a 6 horas en el mar. Por la tarde, playa, snorkel o pesca con mosca (se reserva aparte).',
        },
        { dia: 'Día', numero: String(salida), titulo: 'Regreso', texto: 'Dejas el hotel entre las 11:00 y las 12:00 y te llevamos al aeropuerto.' },
      ],
    }
    : {
      tipo: 'dias',
      titulo: 'Your trip, day by day',
      items: [
        { dia: 'Day', numero: '1', titulo: 'Arrival', texto: 'We pick you up at the airport and take you to Hotel Casa Arrecife. Check-in from 2:00 to 3:00 pm.' },
        {
          dia: 'Days', numero: `2–${ultimoDiaMar}`, titulo: 'Orca and marine life seafari',
          texto: 'You leave between 7:00 and 8:00 am for 5 to 6 hours at sea. Afternoons: beach, snorkeling or fly fishing (booked separately).',
        },
        { dia: 'Day', numero: String(salida), titulo: 'Departure', texto: 'Check out between 11:00 am and noon and we drive you to the airport.' },
      ],
    };
}

const BLOQUES: Record<string, Record<Locale, BloqueDetalle[]>> = {
  'servicio:la-ventana-travel/pesca-con-mosca': {
    es: [
      {
        tipo: 'filas',
        titulo: 'Qué se pesca y cuándo',
        items: [
          { valor: 'Pez gallo', texto: 'Meses por confirmar' },
          { valor: 'Jurel y pargo', texto: 'Meses por confirmar' },
          { valor: 'Dorado y bonito', texto: 'Meses por confirmar' },
        ],
        nota: 'Captura y liberación: por confirmar.',
      },
      {
        tipo: 'incluye',
        titulo: 'Equipo y guía',
        items: [
          { titulo: 'Caña y carrete', estado: 'pendiente', detalle: 'Por confirmar si se incluyen' },
          { titulo: 'Moscas y líneas', estado: 'pendiente', detalle: 'Por confirmar' },
          { titulo: 'Guía de pesca a bordo', estado: 'pendiente', detalle: 'Por confirmar' },
          { titulo: 'Para principiantes y expertos', estado: 'pendiente', detalle: 'Por confirmar' },
        ],
      },
    ],
    en: [
      {
        tipo: 'filas',
        titulo: 'What you catch and when',
        items: [
          { valor: 'Roosterfish', texto: 'Months to be confirmed' },
          { valor: 'Jacks and snapper', texto: 'Months to be confirmed' },
          { valor: 'Mahi-mahi and bonito', texto: 'Months to be confirmed' },
        ],
        nota: 'Catch and release: to be confirmed.',
      },
      {
        tipo: 'incluye',
        titulo: 'Gear and guide',
        items: [
          { titulo: 'Rod and reel', estado: 'pendiente', detalle: 'To be confirmed whether included' },
          { titulo: 'Flies and lines', estado: 'pendiente', detalle: 'To be confirmed' },
          { titulo: 'Fishing guide on board', estado: 'pendiente', detalle: 'To be confirmed' },
          { titulo: 'Beginners and experts', estado: 'pendiente', detalle: 'To be confirmed' },
        ],
      },
    ],
  },
  'paquete:paquete-5-noches': {
    es: [itinerario('es', 5), TEMPORADA.es],
    en: [itinerario('en', 5), TEMPORADA.en],
  },
  'paquete:paquete-7-noches': {
    es: [itinerario('es', 7), TEMPORADA.es],
    en: [itinerario('en', 7), TEMPORADA.en],
  },
};

/** Los bloques propios de un servicio o paquete en un idioma; vacío si no tiene. */
export function bloquesDeDetalle(clave: string, lang: Locale): BloqueDetalle[] {
  return BLOQUES[clave]?.[lang] ?? [];
}
