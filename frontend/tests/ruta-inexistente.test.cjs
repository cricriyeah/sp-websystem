/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { rutaInexistente } = require(path.join(process.env.RUTA_INEXISTENTE_TEST_OUT, 'lib/ruta-inexistente.js'));

test('sedes y empresas que existen pasan', () => {
  assert.equal(rutaInexistente('/es/sede/la-paz'), false);
  assert.equal(rutaInexistente('/en/sede/la-ventana/paquete/paquete-5-noches'), false);
  assert.equal(rutaInexistente('/es/servicio/sal-y-sol/pesca-deportiva'), false);
  assert.equal(rutaInexistente('/es/servicio/la-ventana-travel/algo-nuevo'), false);
});

test('una sede o una empresa que no existe es 404', () => {
  assert.equal(rutaInexistente('/es/sede/cabo'), true);
  assert.equal(rutaInexistente('/en/sede/cabo/paquete/x'), true);
  assert.equal(rutaInexistente('/es/servicio/no-existe/x'), true);
});

test('lo demás no se toca', () => {
  assert.equal(rutaInexistente('/es'), false);
  assert.equal(rutaInexistente('/es/nosotros'), false);
  assert.equal(rutaInexistente('/es/reservar'), false);
});
