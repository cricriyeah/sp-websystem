/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { conIva, ivaDe, porcentajeIva } = require(path.join(process.env.IVA_TEST_OUT, 'lib/iva.js'));
const casos = JSON.parse(fs.readFileSync(path.join(__dirname, '../../shared/precios_paridad.json'), 'utf8'));

test('IVA idéntico al backend para los casos compartidos', () => {
  for (const caso of casos.iva) {
    const { iva, total } = conIva(Number(caso.neto), Number(caso.tasa));
    assert.equal(iva, Number(caso.iva), `iva de ${caso.neto}`);
    assert.equal(total, Number(caso.total), `total de ${caso.neto}`);
  }
});

test('la tasa por defecto es 16 %', () => {
  assert.equal(ivaDe(4500), 720);
  assert.equal(porcentajeIva(), '16');
  assert.equal(porcentajeIva(0.08), '8');
});
