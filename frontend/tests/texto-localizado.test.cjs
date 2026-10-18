/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const t = require(path.join(process.env.TEXTO_LOCALIZADO_TEST_OUT, 'lib/texto-localizado.js'));

test('devuelve el idioma pedido', () => {
  assert.equal(t.textoLocalizado({ es: 'Desayuno', en: 'Breakfast' }, 'es'), 'Desayuno');
  assert.equal(t.textoLocalizado({ es: 'Desayuno', en: 'Breakfast' }, 'en'), 'Breakfast');
});

test('si falta el idioma pedido usa el otro', () => {
  assert.equal(t.textoLocalizado({ es: 'Solo español' }, 'en'), 'Solo español');
  assert.equal(t.textoLocalizado({ en: 'English only' }, 'es'), 'English only');
});

test('un idioma vacío cuenta como faltante', () => {
  assert.equal(t.textoLocalizado({ es: '  ', en: 'Breakfast' }, 'es'), 'Breakfast');
});

test('sin nada devuelve cadena vacía', () => {
  assert.equal(t.textoLocalizado({}, 'es'), '');
  assert.equal(t.textoLocalizado(null, 'en'), '');
  assert.equal(t.textoLocalizado(undefined, 'es'), '');
});
