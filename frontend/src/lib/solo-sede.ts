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
 * `/hub` borra el modo y lleva a la portada (para el dueño y las vendedoras).
 *
 * Todo lo que decide va aquí, puro, para probarlo sin navegador; `proxy.ts` solo lo aplica.
 */

export const COOKIE_SOLO_SEDE = 'sbe_solo_sede';
export const DIAS_SOLO_SEDE = 30;
export const SEGUNDOS_SOLO_SEDE = 60 * 60 * 24 * DIAS_SOLO_SEDE;

/** Link corto → slug de la sede. Una sede nueva se agrega aquí y en `SEDES_SOLO`. */
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

export type DecisionSoloSede =
  | { tipo: 'seguir' }
  /** Redirige; `cookie` dice qué hacer con el modo: guardar una sede o borrarlo. */
  | { tipo: 'redirigir'; destino: string; cookie?: { guardar: string } | 'borrar' };

type Entrada = {
  /** `request.nextUrl.pathname`, tal cual. */
  pathname: string;
  /** `request.nextUrl.search`, con su `?` o vacío. Viaja intacto (el `?ref=` de la vendedora). */
  search: string;
  /** El valor crudo de la cookie, si existe. */
  cookie: string | undefined;
  /** El idioma para una ruta que no lo trae (`/lapaz`): el de `Accept-Language`. */
  idiomaPreferido: Idioma;
};

/**
 * Qué hace el proxy con esta petición. Solo actúa en tres casos y en rutas exactas, para no
 * tocar nada más (checkout, servicios, archivos, regresos de Stripe):
 *
 * 1. Link corto (`/lapaz`, `/en/lapaz`, sin importar mayúsculas ni la diagonal final):
 *    redirige a la sede y guarda el modo.
 * 2. `/hub` (o `/es/hub`, `/en/hub`): borra el modo y va a la portada.
 * 3. Con el modo puesto, la portada (`/`, `/es`, `/en`) y «Sobre nosotros» redirigen a la sede.
 *
 * El destino de cada redirección es una página de sede o la portada sin modo, que no vuelven
 * a caer en ningún caso: no hay forma de encadenar redirecciones.
 */
export function decidirSoloSede({ pathname, search, cookie, idiomaPreferido }: Entrada): DecisionSoloSede {
  const partes = pathname.toLowerCase().split('/').filter(Boolean);
  const conIdioma = IDIOMAS.includes(partes[0] as Idioma);
  const idioma: Idioma = conIdioma ? (partes[0] as Idioma) : idiomaPreferido;
  const resto = conIdioma ? partes.slice(1) : partes;

  if (resto.length === 1) {
    const sede = ENLACES_CORTOS[resto[0]];
    if (sede) return { tipo: 'redirigir', destino: `/${idioma}/sede/${sede}${search}`, cookie: { guardar: sede } };
    if (resto[0] === ENLACE_SALIR) return { tipo: 'redirigir', destino: `/${idioma}${search}`, cookie: 'borrar' };
  }

  const sede = sedeSoloValida(cookie);
  const esPortada = resto.length === 0;
  const esNosotros = conIdioma && resto.length === 1 && resto[0] === 'nosotros';
  if (sede && (esPortada || esNosotros)) {
    return { tipo: 'redirigir', destino: `/${idioma}/sede/${sede}${search}` };
  }

  return { tipo: 'seguir' };
}

/** Lee la sede del modo en el navegador. `null` sin modo o con una cookie que no es de una sede. */
export function leerSoloSedeCliente(): string | null {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${COOKIE_SOLO_SEDE}=([^;]+)`));
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
export const SCRIPT_SOLO_SEDE = `try{var m=document.cookie.match(/(?:^|;\\s*)${COOKIE_SOLO_SEDE}=([^;]+)/);var s=m&&decodeURIComponent(m[1]);if(${JSON.stringify(SEDES_SOLO)}.indexOf(s)>-1)document.body.dataset.soloSede=s}catch(e){}`;
