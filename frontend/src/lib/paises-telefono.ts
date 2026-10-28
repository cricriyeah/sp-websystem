// Lista de países para el selector del teléfono. Módulo puro: la única dependencia es
// libphonenumber-js (build `/min`). Los nombres salen de `Intl.DisplayNames` en el idioma de la
// página; si no existe (o falla), el nombre es la sigla ISO y la lista sigue siendo operable.
import { getCountries, getCountryCallingCode } from 'libphonenumber-js/min';

export type PaisTelefono = {
  /** Sigla ISO 3166-1 alfa-2, p. ej. `MX`. */
  iso: string;
  /** Código de marcación sin `+`, p. ej. `52`. */
  codigo: string;
  /** Nombre en el idioma pedido; la sigla ISO si no hay `Intl.DisplayNames`. */
  nombre: string;
};

/** Fijos arriba de la lista, en este orden. */
export const PAISES_FRECUENTES: readonly string[] = ['MX', 'US', 'CA'];

// Si la biblioteca falla, el selector no se queda vacío: quedan los tres frecuentes.
const RESPALDO: readonly { iso: string; codigo: string }[] = [
  { iso: 'MX', codigo: '52' },
  { iso: 'US', codigo: '1' },
  { iso: 'CA', codigo: '1' },
];

// País que se elige al restaurar un código compartido por varios países. Los demás códigos
// los usa un solo país.
const PRINCIPAL_POR_CODIGO: Record<string, string> = {
  '1': 'US',
  '7': 'RU',
  '39': 'IT',
  '44': 'GB',
  '47': 'NO',
  '61': 'AU',
  '212': 'MA',
  '262': 'RE',
  '290': 'SH',
  '358': 'FI',
  '590': 'GP',
  '599': 'CW',
};

function paisesBase(): { iso: string; codigo: string }[] {
  try {
    return getCountries().map((iso) => ({ iso, codigo: getCountryCallingCode(iso) }));
  } catch {
    return [...RESPALDO];
  }
}

function nombrador(lang: string): (iso: string) => string {
  try {
    const nombres = new Intl.DisplayNames([lang], { type: 'region' });
    return (iso) => {
      try {
        return nombres.of(iso) || iso;
      } catch {
        return iso;
      }
    };
  } catch {
    return (iso) => iso;
  }
}

function comparador(lang: string): (a: string, b: string) => number {
  try {
    return new Intl.Collator(lang).compare;
  } catch {
    return (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  }
}

/** Todos los países con código: México, Estados Unidos y Canadá arriba, el resto alfabético. */
export function listarPaises(lang: string): PaisTelefono[] {
  const nombre = nombrador(lang);
  const comparar = comparador(lang);
  const paises = paisesBase().map(({ iso, codigo }) => ({ iso, codigo, nombre: nombre(iso) }));
  const fijos = PAISES_FRECUENTES.flatMap((iso) => paises.filter((pais) => pais.iso === iso));
  const resto = paises
    .filter((pais) => !PAISES_FRECUENTES.includes(pais.iso))
    .sort((a, b) => comparar(a.nombre, b.nombre));
  return [...fijos, ...resto];
}

/** Código de marcación (sin `+`) de una sigla ISO en mayúsculas. null si no existe. */
export function codigoDePais(iso: string): string | null {
  return paisesBase().find((pais) => pais.iso === iso)?.codigo ?? null;
}

/** País que se elige al restaurar un código (+1 US, +7 RU, +44 GB…). null si no existe. */
export function paisPrincipal(codigo: string): string | null {
  const elegido = PRINCIPAL_POR_CODIGO[codigo];
  if (elegido) return elegido;
  return paisesBase().find((pais) => pais.codigo === codigo)?.iso ?? null;
}

function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim();
}

/**
 * Filtra la lista sin acentos ni mayúsculas, por nombre, por sigla ISO o por código (`+34` o
 * `34`, también parcial). Sin consulta devuelve todo. Conserva el orden de la lista entre
 * resultados del mismo rango; la sigla exacta va primero y luego el nombre que empieza igual.
 */
export function buscarPaises(paises: PaisTelefono[], consulta: string): PaisTelefono[] {
  const q = normalizar(consulta);
  const sinSignos = q.replace(/[+\s]/g, '');
  if (sinSignos === '') return paises;
  if (/^\d+$/.test(sinSignos)) return paises.filter((pais) => pais.codigo.startsWith(sinSignos));
  const rangos: { pais: PaisTelefono; rango: number; orden: number }[] = [];
  paises.forEach((pais, orden) => {
    const nombre = normalizar(pais.nombre);
    let rango = -1;
    if (pais.iso.toLowerCase() === q) rango = 0;
    else if (nombre.startsWith(q)) rango = 1;
    else if (nombre.split(/[\s-]+/).some((palabra) => palabra.startsWith(q))) rango = 2;
    else if (nombre.includes(q)) rango = 3;
    if (rango >= 0) rangos.push({ pais, rango, orden });
  });
  return rangos.sort((a, b) => a.rango - b.rango || a.orden - b.orden).map((r) => r.pais);
}
