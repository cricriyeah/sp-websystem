/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { iniciales } = require(path.join(process.env.INICIALES_TEST_OUT, 'lib/iniciales.js'));

test('las cinco marcas reales', () => {
  assert.equal(iniciales('Sal y Sol Sportfishing'), 'SS');
  assert.equal(iniciales('DLS Transporte'), 'DT');
  assert.equal(iniciales('La Ventana Travel'), 'LV');
  assert.equal(iniciales('Piratas Adventures'), 'PA');
  assert.equal(iniciales('Sun Baja Experience'), 'SB');
});

test('una sola palabra da una sola inicial', () => {
  assert.equal(iniciales('Piratas'), 'P');
});

test('vacío o solo espacios da cadena vacía', () => {
  assert.equal(iniciales(''), '');
  assert.equal(iniciales('   '), '');
});

test('ignora conectores, puntuación y espacios repetidos', () => {
  assert.equal(iniciales('  sal   y   sol '), 'SS');
  assert.equal(iniciales('Viajes de Baja'), 'VB');
  assert.equal(iniciales('Sol & Mar'), 'SM');
  assert.equal(iniciales('(Sal) -- Sol'), 'SS');
});

test('nunca pasa de dos letras', () => {
  assert.equal(iniciales('Uno Dos Tres Cuatro').length, 2);
});

test('acentos y eñes se conservan en mayúscula', () => {
  assert.equal(iniciales('Ñandú Águila'), 'ÑÁ');
});
