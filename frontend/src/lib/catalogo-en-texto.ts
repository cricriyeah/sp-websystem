import type { PaqueteCatalogo, ServicioCatalogo } from './api';
import { formatHour } from './dates';
import { precioPublico } from './iva';
import { aMoneda } from './moneda';
import { formatearPrecio } from './pricing-paquete';

/**
 * Los datos del backoffice dentro de los textos escritos del sitio (pedido del dueño, 2026-11-17: «todo texto que
 * dependa del backoffice cambie dinámicamente con el backoffice»). El texto lleva una marca y el valor sale del
 * catálogo, el mismo que pintan la tarjeta y la ficha del servicio. Así ningún texto repite a mano un dato que la
 * empresa puede cambiar.
 *
 * Marcas, siempre con la clave `<empresa>/<servicio>`:
 * - `{precio:…}` precio base con IVA; `{extra:…}` cargo por persona extra con IVA. En inglés, pesos y su aproximado
 *   en dólares, como en las tarjetas.
 * - `{duracion:…}` la duración de la ficha, dicha en una frase («8 h» se lee «8 horas», «6–7 h», «6 a 7 horas»).
 * - `{personas:…}` cuántas personas cubre el precio; `{maximo:…}` el tope de personas por reserva.
 * - `{anticipo:…}` el porcentaje del anticipo («30 %» / «30%»); no se resuelve si el servicio no acepta anticipo.
 * - `{salida:…}` el punto de salida de la ficha.
 * - `{hora:…}` la primera hora de salida («7:00 am»).
 * - `{horario:…}` la ventana de salida del servicio: «entre las 6:00 y las 7:00 am» / «between 6:00 and 7:00 am».
 *
 * Si una marca no se puede resolver (servicio apagado, campo vacío, catálogo sin respuesta), nada inventa el dato:
 * dentro de una lista (preguntas, párrafos, datos, momentos, filas) se quita el elemento entero; en un texto suelto
 * (un subtítulo, una descripción) se quita solo la frase que lo llevaba.
 */
export type ServicioDeTexto = Pick<ServicioCatalogo,
  'empresa_slug' | 'slug' | 'precio_base' | 'precio_persona_extra' | 'tipo_cambio_usd' | 'personas_incluidas' |
  'permite_anticipo' | 'porcentaje_anticipo'> &
  Partial<Pick<ServicioCatalogo, 'capacidad_maxima' | 'duracion' | 'punto_salida' | 'pide_hora' | 'hora_apertura' | 'hora_cierre'>>;
type Idioma = 'es' | 'en';
type Servicios = readonly ServicioDeTexto[] | null | undefined;

const CAMPOS = ['precio', 'extra', 'duracion', 'personas', 'maximo', 'anticipo', 'salida', 'hora', 'horario'] as const;
type Campo = (typeof CAMPOS)[number];
const MARCA = new RegExp(`\\{(${CAMPOS.join('|')}):([a-z0-9-]+/[a-z0-9-]+)\\}`, 'g');

/**
 * Los servicios de una sede para los textos: los que se venden sueltos y los que solo van dentro de un paquete (el
 * seafari, el hotel), que la lista de servicios no trae. `null` si no respondió ninguna de las dos listas.
 */
export function serviciosParaTexto(
  servicios: readonly ServicioCatalogo[] | null | undefined,
  paquetes: readonly Pick<PaqueteCatalogo, 'servicios_asociados'>[] | null | undefined,
): ServicioCatalogo[] | null {
  if (!servicios && !paquetes) return null;
  const todos = [...(servicios ?? []), ...(paquetes ?? []).flatMap((p) => p.servicios_asociados.map((c) => c.servicio))];
  return todos.filter((s, i) => todos.findIndex((o) => o.empresa_slug === s.empresa_slug && o.slug === s.slug) === i);
}

/** Las claves `<empresa>/<servicio>` que nombran las marcas de un contenido (para pedir solo esas sedes). */
export function clavesDeMarcas(valor: unknown): string[] {
  const claves = new Set<string>();
  const recorrer = (v: unknown) => {
    if (typeof v === 'string') for (const m of v.matchAll(MARCA)) claves.add(m[2]);
    else if (Array.isArray(v)) v.forEach(recorrer);
    else if (v !== null && typeof v === 'object') Object.values(v).forEach(recorrer);
  };
  recorrer(valor);
  return [...claves];
}

function cifra(neto: string, tipoCambio: string, idioma: Idioma): string | null {
  const mxn = precioPublico(aMoneda(neto, 'MXN', tipoCambio));
  if (mxn === null || mxn <= 0) return null;
  const pesos = `${formatearPrecio(mxn, 'MXN')} MXN`;
  if (idioma === 'es') return pesos;
  let usd: number | null;
  try { usd = precioPublico(aMoneda(neto, 'USD', tipoCambio)); } catch { usd = null; }
  return usd ? `${pesos} (about ${formatearPrecio(usd, 'USD')} USD)` : pesos;
}

/** «8 h» → «8 horas», «6–7 h» → «6 a 7 horas», «1 h» → «1 hora». Un texto libre («Día completo») sale tal cual. */
function duracionEnFrase(valor: string, idioma: Idioma): string | null {
  const limpio = valor.trim();
  if (!limpio) return null;
  const m = limpio.match(/^(\d+(?:[.,]\d+)?)(?:\s*[\u2013\u2014-]\s*(\d+(?:[.,]\d+)?))?\s*(?:h|hr|hrs|horas?|hours?)\.?$/i);
  if (!m) return limpio;
  const [, desde, hasta] = m;
  const plural = Boolean(hasta) || desde !== '1';
  const unidad = idioma === 'es' ? (plural ? 'horas' : 'hora') : (plural ? 'hours' : 'hour');
  return hasta ? `${desde} ${idioma === 'es' ? 'a' : 'to'} ${hasta} ${unidad}` : `${desde} ${unidad}`;
}

function valorDe(campo: Campo, servicio: ServicioDeTexto, idioma: Idioma): string | null {
  switch (campo) {
    case 'precio': return cifra(servicio.precio_base, servicio.tipo_cambio_usd, idioma);
    case 'extra': return cifra(servicio.precio_persona_extra, servicio.tipo_cambio_usd, idioma);
    case 'duracion': return servicio.duracion ? duracionEnFrase(servicio.duracion, idioma) : null;
    case 'personas': return servicio.personas_incluidas > 0 ? String(servicio.personas_incluidas) : null;
    case 'maximo': return servicio.capacidad_maxima ? String(servicio.capacidad_maxima) : null;
    case 'anticipo':
      if (!servicio.permite_anticipo || !(servicio.porcentaje_anticipo > 0)) return null;
      return idioma === 'es' ? `${servicio.porcentaje_anticipo} %` : `${servicio.porcentaje_anticipo}%`;
    case 'salida': return servicio.punto_salida?.trim() || null;
    case 'hora': return servicio.pide_hora && servicio.hora_apertura ? formatHour(servicio.hora_apertura) : null;
    case 'horario': {
      if (!servicio.pide_hora || !servicio.hora_apertura || !servicio.hora_cierre) return null;
      const desde = formatHour(servicio.hora_apertura);
      const hasta = formatHour(servicio.hora_cierre);
      if (desde === hasta) return idioma === 'es' ? `a las ${desde}` : `at ${desde}`;
      // «6:00 y 7:00 am»: el primero pierde el «am» cuando los dos lo comparten, como en `ventanaDeSalida`.
      const corto = desde.slice(-2) === hasta.slice(-2) ? desde.slice(0, -3) : desde;
      return idioma === 'es' ? `entre las ${corto} y las ${hasta}` : `between ${corto} and ${hasta}`;
    }
  }
}

const empiezaFrase = (antes: string) => {
  const t = antes.trimEnd();
  return t === '' || /[.!?¿¡:]$/.test(t);
};

/** Mayúscula al inicio de frase y minúscula a media frase, solo para los textos libres (la duración «Día completo»). */
function acomodar(valor: string, antes: string): string {
  if (!/^\p{L}/u.test(valor)) return valor;
  return empiezaFrase(antes) ? valor[0].toUpperCase() + valor.slice(1) : valor[0].toLowerCase() + valor.slice(1);
}

/** Resuelve las marcas de un texto; `falto` dice si alguna no se pudo resolver (su lugar queda vacío). */
function resolver(texto: string, servicios: Servicios, idioma: Idioma): { texto: string; falto: boolean } {
  let falto = false;
  const resuelto = texto.replace(MARCA, (_marca, campo: Campo, clave: string, offset: number) => {
    const servicio = servicios?.find((s) => `${s.empresa_slug}/${s.slug}` === clave);
    const valor = servicio ? valorDe(campo, servicio, idioma) : null;
    if (!valor) { falto = true; return '\u0000'; }
    return campo === 'duracion' || campo === 'horario' ? acomodar(valor, texto.slice(0, offset)) : valor;
  });
  return { texto: resuelto, falto };
}

/** @public Lo usan las pruebas. El texto con sus marcas resueltas, o `null` si alguna no se pudo resolver. */
export function textoConCatalogo(texto: string, servicios: Servicios, idioma: Idioma): string | null {
  const { texto: resuelto, falto } = resolver(texto, servicios, idioma);
  return falto ? null : resuelto;
}

/** Un texto suelto sin las frases cuya marca no se resolvió. */
function sinFrasesFallidas(texto: string): string {
  return texto.split(/(?<=[.!?])\s+/).filter((frase) => !frase.includes('\u0000')).join(' ').trim();
}

const QUITAR = Symbol('quitar');

/**
 * Todo un contenido (una sede, una guía, unas preguntas) con sus marcas resueltas. Ver la regla de arriba para lo
 * que no se puede resolver. Un contenido sin marcas sale igual.
 */
export function conCatalogo<T>(valor: T, servicios: Servicios, idioma: Idioma): T {
  const recorrer = (v: unknown, enLista: boolean): unknown => {
    if (typeof v === 'string') {
      if (!v.includes('{')) return v;
      const { texto, falto } = resolver(v, servicios, idioma);
      if (!falto) return texto;
      return enLista ? QUITAR : sinFrasesFallidas(texto);
    }
    if (Array.isArray(v)) return v.map((x) => recorrer(x, true)).filter((x) => x !== QUITAR);
    if (v !== null && typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype) {
      const campos = Object.entries(v).map(([k, x]) => [k, recorrer(x, enLista)] as const);
      if (enLista && campos.some(([, x]) => x === QUITAR)) return QUITAR;
      return Object.fromEntries(campos);
    }
    return v;
  };
  const resultado = recorrer(valor, false);
  return resultado as T;
}
