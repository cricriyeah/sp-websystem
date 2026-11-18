import type { Locale } from '@/app/[lang]/dictionaries';
import { hrefGuias, hrefInicio, hrefSede } from './routes';
import { ANCLA_DE, ANCLA_HUB } from './secciones-sede';

/**
 * A dónde lleva «volver» en cada página del sitio (PFD, 2026-11-17: «no hay una forma confiable para volver atrás, y
 * no se distingue si vuelve a la sede o al hub»). Sigue un mapa fijo del sitio, nunca el historial del navegador: quien
 * llegó desde un anuncio volvía a Instagram. Siempre dice su destino y lleva al lugar con opciones más cercano:
 *
 * - inicio: no hay regreso;
 * - sede: todos los destinos (`soloHub`: en modo «solo sede» la esquina sigue siendo el logo, la sede es el tope);
 * - detalle de servicio o paquete: su sede, en «Qué reservar»;
 * - guía: la sede de la guía, en «Antes de venir» (sin sede, el índice de guías);
 * - legales: la página del sitio de la que se vino; si no hay, la sede o todos los destinos;
 * - lo demás (índice de guías, nosotros, catálogo): la sede si hay, si no todos los destinos.
 */
export type Regreso = {
  href: string;
  /** El nombre corto que va en la esquina de la barra, en el hueco de las letras del logo («La Paz», «Destinos»). */
  etiqueta: string;
  /** Lo que lee el lector de pantalla («Volver a La Paz»). */
  aria: string;
  /** Lleva al inicio: en modo «solo sede» la esquina vuelve a ser el logo, que ahí lleva a la sede. */
  soloHub?: boolean;
};

/** Un destino sin nombre propio: la etiqueta corta de la barra y la frase completa para el lector de pantalla. */
export type EtiquetaRegreso = { corto: string; aria: string };

export type TextosRegreso = {
  /** «Volver a {destino}», para los destinos con nombre propio (la sede). */
  aria: string;
  destinos: EtiquetaRegreso;
  guias: EtiquetaRegreso;
  anterior: EtiquetaRegreso;
};

const conNombre = (textos: { aria: string }, nombre: string) => ({ etiqueta: nombre, aria: textos.aria.replace('{destino}', nombre) });
const sinNombre = (e: EtiquetaRegreso) => ({ etiqueta: e.corto, aria: e.aria });

type Entrada = {
  lang: Locale;
  /** `usePathname()`, con el idioma: `/es/servicio/sal-y-sol/pesca-deportiva`. */
  ruta: string;
  /** La sede de la página (o la del modo «solo sede»), con su nombre. */
  sede?: { slug: string; nombre: string } | null;
  /** La página anterior del sitio en esta pestaña (ruta con su búsqueda), solo para las legales. */
  anterior?: string | null;
  textos: TextosRegreso;
};

const LEGALES = new Set(['privacidad', 'deslinde', 'cancelaciones']);

/** La primera parte de la ruta tras el idioma (`servicio`, `sede`, `guias`…) y el resto. */
function partes(ruta: string): string[] {
  return ruta.split(/[?#]/)[0].split('/').filter(Boolean).slice(1);
}

export function esLegal(ruta: string): boolean {
  return LEGALES.has(partes(ruta)[0] ?? '');
}

export function regresoDe({ lang, ruta, sede, anterior, textos }: Entrada): Regreso | null {
  const [seccion, slug, sub] = partes(ruta);
  const destinos: Regreso = { href: hrefInicio(lang, ANCLA_HUB.sedes), ...sinNombre(textos.destinos), soloHub: true };
  const aSede = (ancla?: string): Regreso => (sede ? { href: hrefSede(lang, sede.slug, ancla), ...conNombre(textos, sede.nombre) } : destinos);

  if (!seccion) return null;
  if (seccion === 'sede' && slug && !sub) return destinos;
  if (seccion === 'servicio' || (seccion === 'sede' && sub === 'paquete')) return aSede(ANCLA_DE.reservar);
  if (seccion === 'guias' && slug) {
    return sede ? aSede(ANCLA_DE.guias) : { href: hrefGuias(lang), ...sinNombre(textos.guias), soloHub: true };
  }
  if (LEGALES.has(seccion)) {
    return anterior && !esLegal(anterior) ? { href: anterior, ...sinNombre(textos.anterior) } : aSede();
  }
  return aSede();
}

/**
 * Cuándo va el logo de la empresa en la barra (PFD, 2026-11-17). La colaboración «flama Sun Baja × empresa» solo tiene
 * sentido cuando la esquina es nuestro logo: junto al regreso se leía «DESTINOS × SAL Y SOL» y, sin la equis, el logo
 * quedaba suelto. Sin regreso (inicio), siempre; con un regreso al inicio (`soloHub`), solo en modo «solo sede», donde
 * la esquina vuelve a ser el logo; con cualquier otro regreso, nunca: la empresa va en la página (héroe de la sede,
 * encabezado de la compra).
 */
export function empresaEnBarra(regreso: { soloHub?: boolean } | null): 'siempre' | 'solo-sede' | 'nunca' {
  if (!regreso) return 'siempre';
  return regreso.soloHub ? 'solo-sede' : 'nunca';
}

/**
 * El nombre del destino de un enlace de regreso ya armado (el «salir» del checkout, `lib/origen.ts`): la sede por su
 * nombre, el inicio como «Destinos», un servicio o un paquete por lo que es. Etiquetas cortas: van en la esquina de la
 * barra, junto a la flama. `null` si no lo reconoce.
 */
export function etiquetaDeHref(
  href: string,
  sedes: Readonly<Record<string, { nombre: string }>>,
  textos: { aria: string; destinos: EtiquetaRegreso; servicio: EtiquetaRegreso; paquete: EtiquetaRegreso },
): { etiqueta: string; aria: string; soloHub?: boolean } | null {
  const [seccion, slug, sub] = partes(href);
  if (!seccion) return { ...sinNombre(textos.destinos), soloHub: true };
  if (seccion === 'sede' && slug && sub === 'paquete') return sinNombre(textos.paquete);
  if (seccion === 'sede' && slug) return sedes[slug] ? conNombre(textos, sedes[slug].nombre) : null;
  if (seccion === 'servicio') return sinNombre(textos.servicio);
  return null;
}
