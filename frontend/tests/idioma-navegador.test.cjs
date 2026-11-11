/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { idiomaDeCabecera } = require(path.join(process.env.IDIOMA_NAVEGADOR_TEST_OUT, 'lib/idioma-navegador.js'));

test('español e inglés se respetan', () => {
  assert.equal(idiomaDeCabecera('es-MX,es;q=0.9'), 'es');
  assert.equal(idiomaDeCabecera('en-US,en;q=0.9'), 'en');
});

test('sin cabecera queda el español', () => {
  assert.equal(idiomaDeCabecera(''), 'es');
  assert.equal(idiomaDeCabecera(null), 'es');
  assert.equal(idiomaDeCabecera(undefined), 'es');
});

test('quien no lee ninguno de los dos recibe inglés', () => {
  assert.equal(idiomaDeCabecera('fr-FR,fr;q=0.9'), 'en');
  assert.equal(idiomaDeCabecera('de'), 'en');
  assert.equal(idiomaDeCabecera('*'), 'en');
});

test('el primero de los dos en su lista manda, por orden y por peso', () => {
  assert.equal(idiomaDeCabecera('de, es'), 'es');
  assert.equal(idiomaDeCabecera('fr, en;q=0.8, es;q=0.5'), 'en');
  assert.equal(idiomaDeCabecera('en;q=0.3, es;q=0.7'), 'es');
  assert.equal(idiomaDeCabecera('es;q=0, en'), 'en');
});
