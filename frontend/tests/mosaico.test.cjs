/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.MOSAICO_TEST_OUT, 'lib/mosaico.js'));

test('tamanosDeFilas: alterna 2 y 3, y nunca deja una foto sola salvo que sea la única', () => {
  assert.deepEqual(m.tamanosDeFilas(1), [1]);
  assert.deepEqual(m.tamanosDeFilas(2), [2]);
  assert.deepEqual(m.tamanosDeFilas(3), [3]);
  assert.deepEqual(m.tamanosDeFilas(4), [2, 2]);
  assert.deepEqual(m.tamanosDeFilas(6), [2, 4]);
  assert.deepEqual(m.tamanosDeFilas(5), [2, 3]);
  assert.deepEqual(m.tamanosDeFilas(9), [2, 3, 2, 2]);
  for (let n = 1; n <= 20; n++) {
    const filas = m.tamanosDeFilas(n);
    assert.equal(filas.reduce((a, b) => a + b, 0), n, `n=${n}`);
    if (n > 1) assert.ok(filas.every((f) => f >= 2), `n=${n}: ${filas}`);
  }
});

test('columnasDeMosaico: una columna por foto y cada fila suma 12', () => {
  for (let n = 1; n <= 20; n++) {
    const columnas = m.columnasDeMosaico(n);
    assert.equal(columnas.length, n);
    let suma = 0;
    const filas = m.tamanosDeFilas(n);
    let i = 0;
    for (const tamano of filas) {
      suma = columnas.slice(i, i + tamano).reduce((a, b) => a + b, 0);
      assert.equal(suma, 12, `n=${n}`);
      i += tamano;
    }
  }
  assert.deepEqual(m.columnasDeMosaico(5), [7, 5, 4, 4, 4]);
});
