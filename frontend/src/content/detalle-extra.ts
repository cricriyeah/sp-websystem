import 'server-only';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { BloqueLista } from '@/components/detalle-producto';

/**
 * Listas que el detalle de un servicio o paquete pinta después de «Qué incluye» (plan de marketing, puntos 15 y 16):
 * qué se pesca y con qué equipo en la pesca con mosca; el itinerario día por día y la temporada en los paquetes.
 * La clave es la de `imagenes-catalogo.ts` (`servicio:<empresa>/<servicio>` o `paquete:<slug>`).
 *
 * Los itinerarios salen de lo que ya dice la página de La Ventana (seafari del día 2 al 5 o al 7, entrada al hotel
 * de 14:00 a 15:00, salida de 11:00 a 12:00) y la temporada, del dueño (2026-11-11). Lo de la pesca con mosca es de
 * RELLENO hasta que La Ventana Travel confirme especies, meses, equipo y guía: cada renglón dice «por confirmar».
 */
const BLOQUES: Record<string, Record<Locale, BloqueLista[]>> = {
  'servicio:la-ventana-travel/pesca-con-mosca': {
    es: [
      {
        titulo: 'Qué se pesca y cuándo',
        items: [
          { titulo: 'Pez gallo: meses por confirmar' },
          { titulo: 'Jurel y pargo: meses por confirmar' },
          { titulo: 'Dorado y bonito: meses por confirmar' },
          { titulo: 'Captura y liberación: por confirmar' },
        ],
      },
      {
        titulo: 'Equipo y guía',
        items: [
          { titulo: 'Caña y carrete: por confirmar si se incluyen' },
          { titulo: 'Moscas y líneas: por confirmar' },
          { titulo: 'Guía de pesca a bordo: por confirmar' },
          { titulo: 'Nivel: para principiantes y expertos (por confirmar)' },
        ],
      },
    ],
    en: [
      {
        titulo: 'What you catch and when',
        items: [
          { titulo: 'Roosterfish: months to be confirmed' },
          { titulo: 'Jacks and snapper: months to be confirmed' },
          { titulo: 'Mahi-mahi and bonito: months to be confirmed' },
          { titulo: 'Catch and release: to be confirmed' },
        ],
      },
      {
        titulo: 'Gear and guide',
        items: [
          { titulo: 'Rod and reel: to be confirmed whether included' },
          { titulo: 'Flies and lines: to be confirmed' },
          { titulo: 'Fishing guide on board: to be confirmed' },
          { titulo: 'Level: beginners and experts (to be confirmed)' },
        ],
      },
    ],
  },
  'paquete:paquete-5-noches': {
    es: [
      {
        titulo: 'Tu viaje, día por día',
        items: [
          { titulo: 'Día 1: te recogemos en el aeropuerto y llegas al Hotel Casa Arrecife (entrada de 14:00 a 15:00)' },
          { titulo: 'Días 2 a 5: seafari de orcas y fauna marina, de 7:00 u 8:00 am, de 5 a 6 horas' },
          { titulo: 'Tardes libres: playa, snorkel o pesca con mosca (se reserva aparte)' },
          { titulo: 'Día 6: salida del hotel de 11:00 a 12:00 y traslado al aeropuerto' },
        ],
      },
      {
        titulo: 'Temporada',
        items: [
          { titulo: 'Orcas: todo el año' },
          { titulo: 'Ballenas jorobadas y mobulas: desde abril' },
        ],
      },
    ],
    en: [
      {
        titulo: 'Your trip, day by day',
        items: [
          { titulo: 'Day 1: airport pickup and check-in at Hotel Casa Arrecife (2:00 to 3:00 pm)' },
          { titulo: 'Days 2 to 5: orca and marine life seafari, leaving at 7:00 or 8:00 am, 5 to 6 hours' },
          { titulo: 'Free afternoons: beach, snorkeling or fly fishing (booked separately)' },
          { titulo: 'Day 6: check-out from 11:00 am to noon and transfer to the airport' },
        ],
      },
      {
        titulo: 'Season',
        items: [
          { titulo: 'Orcas: year-round' },
          { titulo: 'Humpback whales and mobula rays: from April' },
        ],
      },
    ],
  },
  'paquete:paquete-7-noches': {
    es: [
      {
        titulo: 'Tu viaje, día por día',
        items: [
          { titulo: 'Día 1: te recogemos en el aeropuerto y llegas al Hotel Casa Arrecife (entrada de 14:00 a 15:00)' },
          { titulo: 'Días 2 a 7: seafari de orcas y fauna marina, de 7:00 u 8:00 am, de 5 a 6 horas' },
          { titulo: 'Tardes libres: playa, snorkel o pesca con mosca (se reserva aparte)' },
          { titulo: 'Día 8: salida del hotel de 11:00 a 12:00 y traslado al aeropuerto' },
        ],
      },
      {
        titulo: 'Temporada',
        items: [
          { titulo: 'Orcas: todo el año' },
          { titulo: 'Ballenas jorobadas y mobulas: desde abril' },
        ],
      },
    ],
    en: [
      {
        titulo: 'Your trip, day by day',
        items: [
          { titulo: 'Day 1: airport pickup and check-in at Hotel Casa Arrecife (2:00 to 3:00 pm)' },
          { titulo: 'Days 2 to 7: orca and marine life seafari, leaving at 7:00 or 8:00 am, 5 to 6 hours' },
          { titulo: 'Free afternoons: beach, snorkeling or fly fishing (booked separately)' },
          { titulo: 'Day 8: check-out from 11:00 am to noon and transfer to the airport' },
        ],
      },
      {
        titulo: 'Season',
        items: [
          { titulo: 'Orcas: year-round' },
          { titulo: 'Humpback whales and mobula rays: from April' },
        ],
      },
    ],
  },
};

/** Las listas propias de un servicio o paquete en un idioma; vacía si no tiene. */
export function bloquesDeDetalle(clave: string, lang: Locale): BloqueLista[] {
  return BLOQUES[clave]?.[lang] ?? [];
}
