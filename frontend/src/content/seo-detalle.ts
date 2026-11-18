// Lo que cada página de detalle (servicio o paquete) le dice al buscador además del nombre del catálogo.
//
// El nombre viene del backoffice y es corto («Pesca deportiva», «Seafari 5 noches»): no dice dónde ni qué se busca.
// Aquí va, por producto, el título de la pestaña (lo que se ve en Google) y el renglón pequeño que acompaña al nombre
// dentro del `h1` (auditoría SEO, 2026-11-13). Cada detalle apunta a una búsqueda distinta de la de su sede: la sede
// lleva el término amplio («pesca deportiva en La Paz») y el detalle, el de quien ya compara («precio», «paquete»).
// Un producto sin entrada usa la plantilla general del diccionario (`meta.servicioTitulo`, `meta.paqueteTitulo`).

type Idioma = 'es' | 'en';
type Texto = Record<Idioma, string>;

export type SeoDetalle = {
  /** Título completo de la pestaña, ya con la marca o la empresa: 62 caracteres como máximo. */
  titulo: Texto;
  /** El renglón pequeño sobre el nombre, dentro del `h1`: qué es y dónde. */
  encabezado: Texto;
};

const SERVICIOS: Record<string, SeoDetalle> = {
  'sal-y-sol/pesca-deportiva': {
    titulo: {
      es: 'Precio del tour de pesca en La Paz: panga privada | Sal y Sol',
      en: 'La Paz Fishing Charter Prices: Private Panga Trip | Sal y Sol',
    },
    encabezado: {
      es: 'Pesca en panga privada en La Paz',
      en: 'Private panga fishing charter in La Paz',
    },
  },
  'la-ventana-travel/pesca-con-mosca': {
    titulo: {
      es: 'Pesca con mosca en La Ventana, BCS: día completo en lancha',
      en: 'Fly Fishing in La Ventana, Baja: Full-Day Charter for 1 to 3',
    },
    encabezado: {
      es: 'Día completo en La Ventana, Baja California Sur',
      en: 'Full-day charter in La Ventana, Baja California Sur',
    },
  },
  'piratas-adventures/avistamiento-ballenas': {
    titulo: {
      es: 'Tour de ballena gris en Puerto Chale, Bahía Magdalena: precio',
      en: 'Gray Whale Watching Tour in Puerto Chale, Mag Bay: Prices',
    },
    encabezado: {
      es: 'Tour de ballena gris en Bahía Magdalena',
      en: 'Gray whale tour on Magdalena Bay',
    },
  },
  'piratas-adventures/pesca-deportiva': {
    titulo: {
      // «Puerto Chale» y «Mag Bay» al inicio: en esas búsquedas no sale ningún operador (estudio, 2026-11-16).
      // Bahía Almejas y las especies: dueño, 2026-11-17.
      es: 'Pesca en Puerto Chale, Bahía Almejas: atún, marlín y pargo',
      en: 'Puerto Chale Fishing Charter, Mag Bay: Tuna, Marlin, Snapper',
    },
    encabezado: {
      // El nombre del servicio («Pesca deportiva») va debajo: aquí solo el lugar, sin repetirlo.
      es: 'Puerto Chale, Bahía Almejas',
      en: 'Puerto Chale, Bahía Almejas (Mag Bay)',
    },
  },
  'piratas-adventures/safari-marino': {
    titulo: {
      es: 'Safari marino en Bahía Magdalena: lobos marinos e islas',
      en: 'Magdalena Bay Marine Safari: Sea Lions and Islands by Boat',
    },
    encabezado: {
      es: '{duracion:piratas-adventures/safari-marino} entre las islas de Bahía Magdalena',
      en: '{duracion:piratas-adventures/safari-marino} among the islands of Magdalena Bay',
    },
  },
};

const PAQUETES: Record<string, SeoDetalle> = {
  'la-ventana/paquete-5-noches': {
    titulo: {
      // Noches, hotel y salidas al mar, por persona: lo que distingue al paquete de un cuarto de hotel (estudio,
      // 2026-11-16). Las salidas son las de `detalle-extra.ts`: del día 2 a la última noche.
      es: 'La Ventana 5 noches: hotel y 4 salidas con orcas, por persona',
      en: 'La Ventana 5 Nights: Hotel + 4 Orcas Trips, Price per Person',
    },
    encabezado: {
      es: 'Paquete de seafari y nado con orcas en La Ventana',
      en: 'Orca seafari and swim package in La Ventana',
    },
  },
  'la-ventana/paquete-7-noches': {
    titulo: {
      es: 'La Ventana 7 noches: hotel y 6 salidas con orcas, por persona',
      en: 'La Ventana 7 Nights: Hotel + 6 Orcas Trips, Price per Person',
    },
    encabezado: {
      es: 'Paquete de seafari y nado con orcas en La Ventana',
      en: 'Orca seafari and swim package in La Ventana',
    },
  },
};

/** @public Lo usan las pruebas. Largo máximo del título de pestaña: más allá, Google lo corta. */
export const LARGO_TITULO = 62;

export function seoDeServicio(empresa: string, servicio: string): SeoDetalle | undefined {
  const clave = `${empresa}/${servicio}`;
  return Object.hasOwn(SERVICIOS, clave) ? SERVICIOS[clave] : undefined;
}

export function seoDePaquete(sede: string, paquete: string): SeoDetalle | undefined {
  const clave = `${sede}/${paquete}`;
  return Object.hasOwn(PAQUETES, clave) ? PAQUETES[clave] : undefined;
}

/** @public Lo usan las pruebas: todos los títulos, para medir su largo y que no se repitan. */
export const TODOS_LOS_SEO_DE_DETALLE: readonly SeoDetalle[] = [...Object.values(SERVICIOS), ...Object.values(PAQUETES)];
