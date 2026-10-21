/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CIFRA_TEST_OUT, 'lib/cifra.js'));

test('partirCifra: número y sufijo; sin número no cuenta', () => {
  assert.deepEqual(c.partirCifra('30 %'), { valor: 30, sufijo: ' %' });
  assert.deepEqual(c.partirCifra('48 h'), { valor: 48, sufijo: ' h' });
  assert.deepEqual(c.partirCifra('100'), { valor: 100, sufijo: '' });
  assert.equal(c.partirCifra('Total'), null);
});

test('valorContado: de 0 a la meta, sin pasarse, rápido al principio', () => {
  assert.equal(c.valorContado(48, 0), 0);
  assert.equal(c.valorContado(48, 1), 48);
  assert.equal(c.valorContado(48, 2), 48);
  assert.equal(c.valorContado(48, -1), 0);
  assert.ok(c.valorContado(100, 0.5) > 50);
});
