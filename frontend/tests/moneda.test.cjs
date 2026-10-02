/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { aMoneda } = require(path.join(process.env.MONEDA_TEST_OUT, 'lib/moneda.js'));
const casos = JSON.parse(fs.readFileSync(path.join(__dirname, '../../shared/precios_paridad.json'), 'utf8'));

test('conversión idéntica al backend para los casos compartidos', () => {
  for (const caso of casos.conversiones) {
    assert.equal(aMoneda(caso.monto, caso.moneda, caso.tipo_cambio), Number(caso.esperado));
  }
});

test('la conversión USD exige tipo de cambio positivo y MXN conserva centavos', () => {
  assert.equal(aMoneda('1000.25', 'MXN', null), 1000.25);
  assert.equal(aMoneda(null, 'USD', '18.0000'), null);
  assert.throws(() => aMoneda('100', 'USD', '0'), /tipo de cambio/i);
});
