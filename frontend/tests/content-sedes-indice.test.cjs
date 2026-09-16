/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const i = require(path.join(process.env.CONTENT_SEDES_INDICE_TEST_OUT, 'content/sedes-indice.js'));

test('la-paz y los-cabos existen en el indice con nombre y empresa fundadora', () => {
  const laPaz = i.getSedeIndice('la-paz');
  const losCabos = i.getSedeIndice('los-cabos');
  assert.ok(laPaz);
  assert.ok(losCabos);
  assert.equal(laPaz.nombre, 'La Paz');
  assert.equal(laPaz.empresaFundadoraNombre, 'Sal y Sol Sportfishing');
  assert.equal(losCabos.empresaFundadoraNombre, 'Tours Cabo');
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(i.getSedeIndice('cancun'), undefined);
  assert.equal(i.getSedeIndice('__proto__'), undefined);
  assert.equal(i.getSedeIndice('constructor'), undefined);
});

test('SLUGS_CON_CONTENIDO trae exactamente la-paz y los-cabos', () => {
  assert.deepEqual([...i.SLUGS_CON_CONTENIDO].sort(), ['la-paz', 'los-cabos']);
});

test('el logo de la-paz apunta al logo real; los-cabos usa null (wordmark generico)', () => {
  assert.equal(i.getSedeIndice('la-paz').logo, '/logos/logo2salysol.webp');
  assert.equal(i.getSedeIndice('los-cabos').logo, null);
});
