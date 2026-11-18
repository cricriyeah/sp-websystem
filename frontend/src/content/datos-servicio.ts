import 'server-only';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { ReglasServicio } from '@/lib/detalle-servicio';

/**
 * Lo que la página de un servicio dice en etiquetas cortas (pedido del dueño, 2026-11-16, tras comparar con los
 * marketplaces de pesca): qué se pesca, con enlace a la guía de esa especie, y las reglas del viaje.
 * La clave es la de `imagenes-catalogo.ts` (`servicio:<empresa>/<servicio>`).
 *
 * Especies: las mismas de la sede («Qué se pesca», `sedes-cuerpo.ts`) y de las guías; si cambian allá, aquí también.
 * Puerto Chale: atún, marlín y pargo (dueño, 2026-11-17). Sin enlace: las guías de especies son de La Paz.
 *
 * Reglas: VACÍAS a propósito hasta que el dueño confirme cada una por servicio (¿te quedas con tu pesca?, ¿la
 * limpian?, ¿niños?, ¿recogida?). Una regla sin dato no se pinta: nada se promete por adivinar.
 */
type Especie = { nombre: Record<Locale, string>; /** El slug en español de su guía, si la tiene. */ guia?: string };

const ESPECIES: Record<string, readonly Especie[]> = {
  'servicio:sal-y-sol/pesca-deportiva': [
    { nombre: { es: 'Marlín', en: 'Marlin' }, guia: 'pesca-de-marlin-la-paz' },
    { nombre: { es: 'Dorado', en: 'Dorado' }, guia: 'pesca-de-dorado-la-paz' },
    { nombre: { es: 'Jurel', en: 'Yellowtail' }, guia: 'pesca-de-jurel-la-paz' },
    { nombre: { es: 'Sierra', en: 'Sierra' } },
    { nombre: { es: 'Pargo', en: 'Snapper' } },
    { nombre: { es: 'Cabrilla', en: 'Cabrilla' } },
  ],
  'servicio:piratas-adventures/pesca-deportiva': [
    { nombre: { es: 'Atún', en: 'Tuna' } },
    { nombre: { es: 'Marlín', en: 'Marlin' } },
    { nombre: { es: 'Pargo', en: 'Snapper' } },
  ],
  'servicio:la-ventana-travel/pesca-con-mosca': [
    { nombre: { es: 'Pez gallo', en: 'Roosterfish' }, guia: 'pez-gallo-con-mosca-la-ventana' },
    { nombre: { es: 'Jurel', en: 'Yellowtail' } },
    { nombre: { es: 'Pargo', en: 'Snapper' } },
    { nombre: { es: 'Dorado', en: 'Dorado' } },
  ],
};

const REGLAS: Record<string, ReglasServicio> = {};

/**
 * El equipo de pesca, dicho en la ficha y no solo en las preguntas (PFD del detalle, 2026-11-17): quien compara con un
 * marketplace da por hecho que va incluido. Solo lo que el dueño confirmó; sin dato, la ficha no lo dice.
 */
type Equipo = Record<Locale, { valor: string; nota?: string }>;
const EQUIPO: Record<string, Equipo> = {
  // Dueño, 2026-11-10: los clientes de Piratas traen su equipo.
  'servicio:piratas-adventures/pesca-deportiva': {
    es: { valor: 'Traes el tuyo', nota: '¿No tienes? Pregúntanos antes de reservar' },
    en: { valor: 'Bring your own', nota: 'No gear? Ask us before you book' },
  },
};

export function especiesDeServicio(clave: string): readonly Especie[] {
  return ESPECIES[clave] ?? [];
}

export function reglasDeServicio(clave: string): ReglasServicio {
  return REGLAS[clave] ?? {};
}

export function equipoDeServicio(clave: string, lang: Locale): { valor: string; nota?: string } | undefined {
  return EQUIPO[clave]?.[lang];
}
