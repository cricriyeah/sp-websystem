/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { campoDeValidacion } = require(path.join(process.env.CAMPO_VALIDACION_TEST_OUT, 'lib/campo-validacion.js'));

test('identifica validaciones del paquete que la persona puede corregir', () => {
  assert.equal(campoDeValidacion({ numero_personas: ['Máximo 2 personas.'] }), 'personas');
  assert.equal(campoDeValidacion({ hora: ['Hora fuera de rango.'] }), 'hora');
  assert.equal(campoDeValidacion({ fecha: ['Fecha no disponible.'] }), 'fecha');
  assert.equal(campoDeValidacion({ punto_encuentro: ['Elige hotel.'] }), 'traslado');
});

test('ignora detalles tecnicos y respuestas sin un campo conocido', () => {
  assert.equal(campoDeValidacion({ detail: 'error interno' }), null);
  assert.equal(campoDeValidacion(null), null);
});
