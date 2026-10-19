/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const r = require(path.join(process.env.RECONCILIAR_TEST_OUT, 'lib/reconciliar-sedes.js'));

const indice = {
  'la-paz': { slug: 'la-paz', nombre: 'La Paz', empresaProtagonistaSlug: 'sal-y-sol' },
  'la-ventana': { slug: 'la-ventana', nombre: 'La Ventana', empresaProtagonistaSlug: 'la-ventana-travel' },
  'puerto-chale': { slug: 'puerto-chale', nombre: 'Puerto Chale', empresaProtagonistaSlug: 'piratas-adventures' },
};

test('interseccion normal: solo los slugs que la API confirma activos', () => {
  const resultado = r.sedesActivas(indice, [{ slug: 'la-paz' }]);
  assert.deepEqual(resultado.map((s) => s.slug), ['la-paz']);
});

test('la API no trae una sede del indice: esa sede desaparece', () => {
  const resultado = r.sedesActivas(indice, [{ slug: 'la-paz' }, { slug: 'cancun' }]);
  assert.deepEqual(resultado.map((s) => s.slug), ['la-paz']);
});

test('fallo abierto: sedesApi null muestra TODO el indice sin filtrar', () => {
  const resultado = r.sedesActivas(indice, null);
  assert.deepEqual(resultado.map((s) => s.slug).sort(), ['la-paz', 'la-ventana', 'puerto-chale']);
});

test('array vacio de la API (sin fallo, pero sin sedes activas): no muestra ninguna', () => {
  const resultado = r.sedesActivas(indice, []);
  assert.deepEqual(resultado, []);
});

test('devuelve entradas del indice, no las reconstruye', () => {
  const resultado = r.sedesActivas(indice, [{ slug: 'la-paz' }]);
  assert.equal(resultado[0], indice['la-paz']);
});
