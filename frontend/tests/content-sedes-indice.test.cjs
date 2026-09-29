/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const i = require(path.join(process.env.CONTENT_SEDES_INDICE_TEST_OUT, 'content/sedes-indice.js'));

test('la-paz tiene empresa fundadora y las sedes pendientes no inventan una', () => {
  const laPaz = i.getSedeIndice('la-paz');
  const laVentana = i.getSedeIndice('la-ventana');
  assert.ok(laPaz);
  assert.ok(laVentana);
  assert.equal(laPaz.nombre, 'La Paz');
  assert.equal(laPaz.empresaFundadoraNombre, 'Sal y Sol Sportfishing');
  assert.equal(laVentana.empresaFundadoraNombre, null);
  assert.equal(i.getSedeIndice('puerto-chale').empresaFundadoraNombre, null);
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(i.getSedeIndice('cancun'), undefined);
  assert.equal(i.getSedeIndice('__proto__'), undefined);
  assert.equal(i.getSedeIndice('constructor'), undefined);
});

test('SLUGS_CON_CONTENIDO trae La Paz, La Ventana y Puerto Chale', () => {
  assert.deepEqual([...i.SLUGS_CON_CONTENIDO].sort(), ['la-paz', 'la-ventana', 'puerto-chale']);
});

test('el logo de la-paz apunta al logo real; la-ventana usa null (wordmark generico)', () => {
  assert.equal(i.getSedeIndice('la-paz').logo, '/logos/logo2salysol.webp');
  assert.equal(i.getSedeIndice('la-ventana').logo, null);
});
