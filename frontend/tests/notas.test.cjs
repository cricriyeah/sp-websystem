/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { NOTAS_MAX, notasParaEnviar } = require(path.join(process.env.NOTAS_TEST_OUT, 'lib/notas.js'));

test('el tope es el mismo del backend (NOTAS_CLIENTE_MAX)', () => {
  assert.equal(NOTAS_MAX, 500);
});

test('la nota viaja sin espacios de sobra y nunca más larga que el tope', () => {
  assert.equal(notasParaEnviar('  primera vez  '), 'primera vez');
  assert.equal(notasParaEnviar('x'.repeat(600)).length, 500);
  assert.equal(notasParaEnviar(''), '');
});
