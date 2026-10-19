/* eslint-disable @typescript-eslint/no-require-imports */
// Los dos diccionarios tienen las mismas claves (regla 6 de F9: es y en con el mismo orden y peso).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const leer = (lang) =>
  JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'src/app/[lang]/dictionaries', `${lang}.json`), 'utf8'));

function claves(valor, prefijo = '') {
  if (Array.isArray(valor)) return valor.flatMap((v, i) => claves(v, `${prefijo}[${i}]`));
  if (valor && typeof valor === 'object') {
    return Object.entries(valor).flatMap(([k, v]) => claves(v, prefijo ? `${prefijo}.${k}` : k));
  }
  return [prefijo];
}

test('es.json y en.json tienen las mismas claves', () => {
  const es = new Set(claves(leer('es')));
  const en = new Set(claves(leer('en')));
  assert.deepEqual([...es].filter((k) => !en.has(k)), [], 'Solo en es.json');
  assert.deepEqual([...en].filter((k) => !es.has(k)), [], 'Solo en en.json');
});
