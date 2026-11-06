/**
 * Modo «solo sede»: el link corto de una sede (`/lapaz`) deja al cliente dentro de esa sede.
 *
 * Una empresa comparte su link y no quiere que el cliente acabe en el hub, viendo a las otras.
 * Al entrar por el link corto el navegador guarda la sede en una cookie (30 días) y desde
 * ese momento:
 *
 * - el hub y «Sobre nosotros» redirigen a la sede (`proxy.ts`), así que cualquier enlace o URL
 *   escrita a mano que lleve al hub termina en la sede, nunca en un bucle;
 * - el encabezado y el pie esconden lo que solo sirve para salir al hub (clase `sale-al-hub`,
 *   oculta por CSS desde que `<body>` lleva `data-solo-sede`, antes de pintar) y el logo lleva
 *   al inicio de la sede.
 *
 * Si el cliente abre otra sede (un link que le pasó una vendedora), la cookie pasa a esa sede:
 * el modo sigue a la sede que tiene enfrente y nunca mezcla la página de una con el logo de otra.
 * Lo hacen dos piezas, porque ninguna ve todos los casos: el proxy, al cargar una página de otra
 * sede (también el checkout, que no lleva `SiteHeader`: el link directo de la vendedora entra por
 * ahí), y `SiteHeader`, en la navegación sin recarga, que Next puede servir de su caché sin pasar
 * por el proxy.
 * `/hub` borra el modo y lleva a la portada (para el dueño y las vendedoras).
 *
 * Todo lo que decide va aquí, puro, para probarlo sin navegador; `proxy.ts` solo lo aplica.
 */

import { MARCAS } from '../content/empresas-marca';

export const COOKIE_SOLO_SEDE = 'sbe_solo_sede';
export const DIAS_SOLO_SEDE = 30;
export const SEGUNDOS_SOLO_SEDE = 60 * 60 * 24 * DIAS_SOLO_SEDE;

/** Link corto → slug de la sede. Una sede nueva se agrega solo aquí: `SEDES_SOLO` sale de esta lista. */
export const ENLACES_CORTOS: Readonly<Record<string, string>> = {
  lapaz: 'la-paz',
  laventana: 'la-ventana',
  puertochale: 'puerto-chale',
};

/** Las únicas sedes que el modo acepta: una cookie con otro valor se ignora. */
export const SEDES_SOLO: readonly string[] = Object.values(ENLACES_CORTOS);

/** Borra el modo y lleva a la portada. */
export const ENLACE_SALIR = 'hub';

const IDIOMAS = ['es', 'en'] as const;
type Idioma = (typeof IDIOMAS)[number];

export function sedeSoloValida(valor: string | null | undefined): string | null {
  return valor && SEDES_SOLO.includes(valor) ? valor : null;
}

/** `Object.hasOwn`: con un `[]` a secas, `/constructor` o `/__proto__` contaban como link corto. */
function sedeDelEnlace(segmento: string): string | undefined {
  return Object.hasOwn(ENLACES_CORTOS, segmento) ? ENLACES_CORTOS[segmento] : undefined;
}

function sedeDeEmpresa(slug: string | null): string | undefined {
  return slug ? MARCAS.find((marca) => marca.slug === slug)?.sede : undefined;
}

/**
 * La sede de la página pedida, si es de una: la sede misma (y sus paquetes), un servicio y los
 * checkouts. Manda `?sede=`, como en la página; si no viene, la sede de la empresa.
 */
function sedeDeLaPagina(resto: readonly string[], query: URLSearchParams): string | null {
  const [seccion, slug] = resto;
  if (seccion === 'sede') return sedeSoloValida(slug);
  let empresa: string | null;
  if (seccion === 'servicio') empresa = slug ?? null;
  else if (seccion === 'reservar' || seccion === 'traslados') empresa = query.get('empresa') ?? query.get('paquete_empresa');
  else return null;
  return sedeSoloValida(query.get('sede') ?? sedeDeEmpresa(empresa));
}

type CambioCookie = { guardar: string } | 'borrar';

export type DecisionSoloSede =
  /** Sigue; con `cookie`, el modo pasa a la sede de la página. */
  | { tipo: 'seguir'; cookie?: { guardar: string } }
  /** Redirige; `cookie` dice qué hacer con el modo: guardar una sede o borrarlo. */
  | { tipo: 'redirigir'; destino: string; cookie?: CambioCookie };

type Entrada = {
  /** `request.nextUrl.pathname`, tal cual. */
  pathname: string;
  /** `request.nextUrl.search`, con su `?` o vacío. Viaja intacto (el `?ref=` de la vendedora). */
  search: string;
  /** El valor crudo de la cookie, si existe. */
  cookie: string | undefined;
  /**
   * El idioma para una ruta que no lo trae (`/lapaz`): el de `Accept-Language`. Es una función
   * porque casi ninguna petición lo necesita y el proxy corre en todas.
   */
  idiomaPreferido: () => Idioma;
  /**
   * `true` si el navegador carga la página entera (`Sec-Fetch-Dest: document`). Solo entonces el
   * modo pasa a la sede de la página: Next pide por adelantado las páginas de los enlaces visibles
   * con `fetch`, y esa petición no es el cliente abriéndola. (El proxy no ve la cabecera
   * `next-router-prefetch`: Next la quita antes.) La navegación sin recarga la cubre `SiteHeader`.
   */
  esCargaDePagina?: boolean;
};

/**
 * Qué hace el proxy con esta petición. Solo redirige en tres casos y en rutas exactas, para no
 * tocar nada más (checkout, servicios, archivos, regresos de Stripe):
 *
 * 1. Link corto (`/lapaz`, `/en/lapaz`, sin importar mayúsculas ni la diagonal final):
 *    redirige a la sede y guarda el modo.
 * 2. `/hub` (o `/es/hub`, `/en/hub`): borra el modo y va a la portada.
 * 3. Con el modo puesto, la portada (`/`, `/es`, `/en`) y «Sobre nosotros» (con o sin idioma)
 *    redirigen a la sede.
 *
 * Y con el modo puesto, una página de otra sede (`sedeDeLaPagina`) sigue de largo y pasa el modo
 * a esa sede.
 *
 * El destino de cada redirección es una página de sede o la portada sin modo, que no vuelven
 * a caer en ningún caso: no hay forma de encadenar redirecciones.
 */
export function decidirSoloSede({ pathname, search, cookie, idiomaPreferido, esCargaDePagina = true }: Entrada): DecisionSoloSede {
  const partes = pathname.toLowerCase().split('/').filter(Boolean);
  const conIdioma = IDIOMAS.includes(partes[0] as Idioma);
  const idioma = (): Idioma => (conIdioma ? (partes[0] as Idioma) : idiomaPreferido());
  const resto = conIdioma ? partes.slice(1) : partes;

  if (resto.length === 1) {
    const sede = sedeDelEnlace(resto[0]);
    if (sede) return { tipo: 'redirigir', destino: `/${idioma()}/sede/${sede}${search}`, cookie: { guardar: sede } };
    if (resto[0] === ENLACE_SALIR) return { tipo: 'redirigir', destino: `/${idioma()}${search}`, cookie: 'borrar' };
  }

  const sede = sedeSoloValida(cookie);
  if (!sede) return { tipo: 'seguir' };

  // Sin idioma, `/nosotros` va directo a la sede: si siguiera, el proxy le pondría el idioma y la
  // siguiente petición volvería a redirigir (dos saltos en vez de uno).
  const esPortada = resto.length === 0;
  const esNosotros = resto.length === 1 && resto[0] === 'nosotros';
  if (esPortada || esNosotros) return { tipo: 'redirigir', destino: `/${idioma()}/sede/${sede}${search}` };

  const otra = !esCargaDePagina ? null : sedeDeLaPagina(resto, new URLSearchParams(search));
  if (otra && otra !== sede) return { tipo: 'seguir', cookie: { guardar: otra } };

  return { tipo: 'seguir' };
}

// La misma lectura de la cookie en `leerSoloSedeCliente` y en el script en línea.
const PATRON_COOKIE = `(?:^|;\\s*)${COOKIE_SOLO_SEDE}=([^;]+)`;
const REGEX_COOKIE = new RegExp(PATRON_COOKIE);

/** Lee la sede del modo en el navegador. `null` sin modo o con una cookie que no es de una sede. */
export function leerSoloSedeCliente(): string | null {
  try {
    const match = document.cookie.match(REGEX_COOKIE);
    return sedeSoloValida(match ? decodeURIComponent(match[1]) : null);
  } catch {
    return null;
  }
}

/** Pasa el modo a otra sede (el cliente abrió otra). Mismo plazo y forma que la del proxy. */
export function guardarSoloSedeCliente(slug: string): void {
  if (!sedeSoloValida(slug)) return;
  try {
    document.cookie = `${COOKIE_SOLO_SEDE}=${encodeURIComponent(slug)}; path=/; max-age=${SEGUNDOS_SOLO_SEDE}; samesite=lax`;
    document.body.dataset.soloSede = slug;
  } catch {
    // Cookies bloqueadas: el modo simplemente no cambia.
  }
}

/**
 * Script en línea, primero dentro de `<body>`: marca `data-solo-sede` antes de que se pinte el
 * encabezado, así lo que lleva al hub nunca aparece ni un instante. Lee la cookie y la valida
 * contra la misma lista que el proxy.
 */
export const SCRIPT_SOLO_SEDE = `try{var m=document.cookie.match(new RegExp(${JSON.stringify(PATRON_COOKIE)}));var s=m&&decodeURIComponent(m[1]);if(${JSON.stringify(SEDES_SOLO)}.indexOf(s)>-1)document.body.dataset.soloSede=s}catch(e){}`;
