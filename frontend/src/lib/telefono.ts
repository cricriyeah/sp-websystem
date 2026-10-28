// Teléfono con código de país. Módulo puro: la única dependencia es libphonenumber-js
// (build `/min`, importada estática, ver ARCH-telefono-con-pais).
//
// Valor que viaja por el estado, el borrador y el payload: texto compacto `+<código><número>`
// (`+526121234567`), o '' si no hay dígitos. Se valida SOLO el largo por país (`isPossible`):
// bloquear a un cliente real con un número válido es una venta perdida, el servidor revalida.
// Toda llamada a la biblioteca va en try/catch: si falla, se degrada a "7 a 15 dígitos" y
// nunca se bloquea una venta.
import {
  getCountries,
  getCountryCallingCode,
  parseDigits,
  parsePhoneNumberFromString,
  type CountryCode,
} from 'libphonenumber-js/min';

export const PAIS_POR_DEFECTO = 'MX';

// E.164: 15 dígitos entre código y número (más el `+` son 16 caracteres guardados).
const MAX_DIGITOS = 15;
const MIN_DIGITOS_RESPALDO = 7;
// Código de PAIS_POR_DEFECTO. Se fija aquí para que un valor viejo sin código se lea como
// mexicano aunque la biblioteca falle.
const CODIGO_PAIS_DEFECTO = '52';
// Más largo que esto no es un teléfono: se evita trabajo de más con entradas hostiles.
const MAX_ENTRADA = 200;

export type Evaluacion = 'vacio' | 'ok' | 'incompleto' | 'codigo-desconocido';

export type TelefonoFormateado = {
  /** `+52 612 123 4567` */
  texto: string;
  /** Código de marcación sin `+`, p. ej. `52`. */
  codigo: string;
  /** País para la bandera y el nombre; null si la biblioteca no lo precisa (p. ej. +1 sin lada). */
  iso: string | null;
};

type Interpretado =
  | { tipo: 'vacio' }
  | { tipo: 'basura' }
  | { tipo: 'desconocido' }
  // codigo '' = no se pudo verificar contra la tabla de códigos (la biblioteca falló).
  | { tipo: 'numero'; codigo: string; nacional: string };

type Analisis =
  | { estado: 'ok'; posible: boolean; e164: string; internacional: string; pais: string | null }
  | { estado: 'no-parsea' }
  | { estado: 'fallo' };

function soloDigitos(texto: string): string {
  try {
    return parseDigits(texto);
  } catch {
    return texto.replace(/\D/g, '');
  }
}

// La extensión (`ext. 12`, `x12`, `#12`) se descarta: son viajeros y WhatsApp no marca extensiones.
const EXTENSION = /[\s,;]*(?:ext(?:ension|ensión)?\.?|x|#|int\.?)\s*\d+\s*$/iu;

function sinExtension(texto: string): string {
  return texto.length > MAX_ENTRADA ? texto : texto.replace(EXTENSION, '');
}

function llevaCodigo(texto: string): boolean {
  return texto.startsWith('+') || texto.startsWith('00');
}

let tabla: Set<string> | null | undefined;

// Los códigos de marcación son libres de prefijo, así que el primer prefijo de 1 a 3 dígitos
// que esté en la tabla es el código. null = la biblioteca falló y no hay tabla.
function codigosConocidos(): Set<string> | null {
  if (tabla === undefined) {
    try {
      tabla = new Set(getCountries().map((pais) => getCountryCallingCode(pais)));
    } catch {
      tabla = null;
    }
  }
  return tabla;
}

// undefined = sin tabla; null = ningún prefijo es un código.
function buscarCodigo(digitos: string): { codigo: string; resto: string } | null | undefined {
  const conocidos = codigosConocidos();
  if (!conocidos) return undefined;
  for (let largo = 1; largo <= 3 && largo <= digitos.length; largo += 1) {
    const prefijo = digitos.slice(0, largo);
    if (conocidos.has(prefijo)) return { codigo: prefijo, resto: digitos.slice(largo) };
  }
  return null;
}

function interpretar(valor: string): Interpretado {
  const texto = sinExtension(valor.trim());
  // Solo separadores o nada: no hay nada que validar.
  if (!/[^\s+()\-.]/.test(texto)) return { tipo: 'vacio' };
  if (llevaCodigo(texto)) {
    const crudos = soloDigitos(texto.startsWith('+') ? texto.slice(1) : texto.slice(2));
    if (crudos === '') return { tipo: 'vacio' };
    const encontrado = buscarCodigo(crudos);
    if (encontrado === undefined) return { tipo: 'numero', codigo: '', nacional: crudos };
    if (encontrado === null) return { tipo: 'desconocido' };
    if (encontrado.resto === '') return { tipo: 'vacio' };
    return { tipo: 'numero', codigo: encontrado.codigo, nacional: encontrado.resto };
  }
  const digitos = soloDigitos(texto);
  if (digitos === '') return { tipo: 'basura' };
  return { tipo: 'numero', codigo: CODIGO_PAIS_DEFECTO, nacional: digitos };
}

// Reglas de México que la biblioteca no cubre: el `1` móvil de antes (`+52 1 612…`) y los
// prefijos de marcado nacional 01, 044 y 045. Solo actúan si lo que queda mide 10 dígitos,
// así que un número válido nunca cambia (los mexicanos de 10 dígitos no empiezan en 0 ni 1).
function normalizarNacional(codigo: string, nacional: string): string {
  if (codigo !== CODIGO_PAIS_DEFECTO) return nacional;
  if (nacional.length === 11 && nacional.startsWith('1')) return nacional.slice(1);
  for (const prefijo of ['044', '045', '01']) {
    if (nacional.startsWith(prefijo) && nacional.length - prefijo.length === 10) {
      return nacional.slice(prefijo.length);
    }
  }
  return nacional;
}

function analizar(codigo: string, nacional: string): Analisis {
  try {
    const numero = parsePhoneNumberFromString('+' + codigo + nacional);
    if (!numero) return { estado: 'no-parsea' };
    return {
      estado: 'ok',
      posible: numero.isPossible(),
      e164: numero.number,
      internacional: numero.formatInternational(),
      pais: numero.country ?? null,
    };
  } catch {
    return { estado: 'fallo' };
  }
}

function enRespaldo(total: number): boolean {
  return total >= MIN_DIGITOS_RESPALDO && total <= MAX_DIGITOS;
}

/** Resultado de validar lo que hay en el campo. Nunca lanza. */
export function evaluar(valor: string): Evaluacion {
  const i = interpretar(valor);
  if (i.tipo === 'vacio') return 'vacio';
  if (i.tipo === 'desconocido') return 'codigo-desconocido';
  if (i.tipo === 'basura') return 'incompleto';
  const total = i.codigo.length + i.nacional.length;
  if (total > MAX_DIGITOS) return 'incompleto';
  if (i.codigo === '') return enRespaldo(total) ? 'ok' : 'incompleto';
  const analisis = analizar(i.codigo, normalizarNacional(i.codigo, i.nacional));
  if (analisis.estado === 'fallo') return enRespaldo(total) ? 'ok' : 'incompleto';
  return analisis.estado === 'ok' && analisis.posible ? 'ok' : 'incompleto';
}

/**
 * Separa el código de país de un texto que empieza con `+` o `00` (tecleado, pegado o
 * autocompletado). null si no empieza así, si el código no existe o si la biblioteca falló.
 */
export function resolverCodigo(texto: string): { codigo: string; resto: string } | null {
  const limpio = sinExtension(texto.trim());
  if (!llevaCodigo(limpio)) return null;
  const crudos = soloDigitos(limpio.startsWith('+') ? limpio.slice(1) : limpio.slice(2));
  return buscarCodigo(crudos) ?? null;
}

/**
 * Arma el valor compacto. '' mientras no haya dígitos (el país solo no cuenta como valor).
 * Conserva el cero inicial tecleado, descarta letras y extensión, pasa dígitos no ASCII a
 * ASCII y topa en 15 dígitos entre código y número.
 */
export function compactar(codigo: string, texto: string): string {
  const prefijo = soloDigitos(codigo);
  const digitos = soloDigitos(sinExtension(texto)).slice(0, Math.max(0, MAX_DIGITOS - prefijo.length));
  return digitos === '' ? '' : '+' + prefijo + digitos;
}

/** `+<código><número>` canónico si es un número posible; null si no (o si la biblioteca falló). */
export function aE164(valor: string): string | null {
  const i = interpretar(valor);
  if (i.tipo !== 'numero' || i.codigo === '') return null;
  if (i.codigo.length + i.nacional.length > MAX_DIGITOS) return null;
  const analisis = analizar(i.codigo, normalizarNacional(i.codigo, i.nacional));
  return analisis.estado === 'ok' && analisis.posible ? analisis.e164 : null;
}

/** Lo que va al servidor: E.164 si parsea; si no, el texto recortado tal cual (nunca se vacía). */
export function telefonoParaEnviar(valor: string): string {
  return aE164(valor) ?? valor.trim();
}

/**
 * Pasa un valor guardado (borrador, reanudación, servidor) al compacto. Jamás borra lo que
 * había: lo que no se puede interpretar vuelve recortado y el campo lo muestra con México.
 */
export function restaurarTelefono(valor: string): string {
  const i = interpretar(valor);
  if (i.tipo === 'vacio') return '';
  if (i.tipo !== 'numero') return valor.trim();
  const canonico = aE164(valor);
  if (canonico) return canonico;
  if (i.codigo === '' || i.codigo.length + i.nacional.length > MAX_DIGITOS) return valor.trim();
  return '+' + i.codigo + normalizarNacional(i.codigo, i.nacional);
}

function mismoCodigo(iso: string, codigo: string): boolean {
  try {
    return getCountryCallingCode(iso as CountryCode) === codigo;
  } catch {
    return false;
  }
}

/**
 * `+52 612 123 4567` con el país. `iso` es el país que el cliente eligió en el selector; se
 * respeta si su código coincide (GB, GG, IM y JE comparten +44). null si no hay un número
 * posible: el llamador lo muestra tal cual.
 */
export function formatearTelefono(valor: string, iso?: string): TelefonoFormateado | null {
  const i = interpretar(valor);
  if (i.tipo !== 'numero' || i.codigo === '') return null;
  if (i.codigo.length + i.nacional.length > MAX_DIGITOS) return null;
  const analisis = analizar(i.codigo, normalizarNacional(i.codigo, i.nacional));
  if (analisis.estado !== 'ok' || !analisis.posible) return null;
  const elegido = iso && mismoCodigo(iso, i.codigo) ? iso : analisis.pais;
  return { texto: analisis.internacional, codigo: i.codigo, iso: elegido };
}
