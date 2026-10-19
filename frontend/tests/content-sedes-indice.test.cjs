/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const i = require(path.join(process.env.CONTENT_SEDES_INDICE_TEST_OUT, 'content/sedes-indice.js'));

test('cada sede tiene su empresa protagonista (decisión del dueño, 2026-10-16)', () => {
  assert.equal(i.getSedeIndice('la-paz').nombre, 'La Paz');
  assert.equal(i.getSedeIndice('la-paz').empresaProtagonistaSlug, 'sal-y-sol');
  assert.equal(i.getSedeIndice('la-ventana').empresaProtagonistaSlug, 'la-ventana-travel');
  assert.equal(i.getSedeIndice('puerto-chale').empresaProtagonistaSlug, 'piratas-adventures');
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(i.getSedeIndice('cancun'), undefined);
  assert.equal(i.getSedeIndice('__proto__'), undefined);
  assert.equal(i.getSedeIndice('constructor'), undefined);
});

test('SLUGS_CON_CONTENIDO trae La Paz, La Ventana y Puerto Chale', () => {
  assert.deepEqual([...i.SLUGS_CON_CONTENIDO].sort(), ['la-paz', 'la-ventana', 'puerto-chale']);
});

test('el índice no duplica nombre ni logo de la empresa (salen de empresas-marca)', () => {
  assert.equal(i.getSedeIndice('la-paz').logo, undefined);
  assert.equal(i.getSedeIndice('la-paz').empresaFundadoraNombre, undefined);
});
