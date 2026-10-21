/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const f = require(path.join(process.env.FILA_ARRASTRABLE_TEST_OUT, 'lib/fila-arrastrable.js'));

test('estadoDeFila: si todo cabe no desborda ni hay flechas', () => {
  assert.deepEqual(f.estadoDeFila({ scrollLeft: 0, scrollWidth: 1000, clientWidth: 1000 }), {
    desborda: false, avance: 1, puedeAtras: false, puedeAdelante: false,
  });
  assert.equal(f.estadoDeFila({ scrollLeft: 0, scrollWidth: 1001, clientWidth: 1000 }).desborda, false);
});

test('estadoDeFila: al inicio solo hay adelante; al final solo atrás', () => {
  const inicio = f.estadoDeFila({ scrollLeft: 0, scrollWidth: 2000, clientWidth: 500 });
  assert.equal(inicio.desborda, true);
  assert.equal(inicio.puedeAtras, false);
  assert.equal(inicio.puedeAdelante, true);
  assert.equal(inicio.avance, 0.25);
  const final = f.estadoDeFila({ scrollLeft: 1500, scrollWidth: 2000, clientWidth: 500 });
  assert.equal(final.puedeAtras, true);
  assert.equal(final.puedeAdelante, false);
  assert.equal(final.avance, 1);
});

test('destinoDeFila: avanza el 80 % del carril y no pasa de los extremos', () => {
  const m = { scrollLeft: 0, scrollWidth: 2000, clientWidth: 500 };
  assert.equal(f.destinoDeFila(m, 1), 400);
  assert.equal(f.destinoDeFila(m, -1), 0);
  assert.equal(f.destinoDeFila({ ...m, scrollLeft: 1400 }, 1), 1500);
  assert.equal(f.destinoDeFila({ ...m, scrollLeft: 300 }, -1), 0);
});
