/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const t = require(path.join(process.env.TEMPORADA_TEST_OUT, 'lib/temporada-actual.js'));

const es = [{ meses: ['Dic', 'Ene', 'Feb', 'Mar'] }, { meses: ['Abr', 'May', 'Jun'] }, { meses: ['Jul', 'Ago', 'Sep'] }, { meses: ['Oct', 'Nov'] }];
const en = [{ meses: ['Dec', 'Jan', 'Feb', 'Mar'] }, { meses: ['Apr', 'May', 'Jun'] }, { meses: ['Jul', 'Aug', 'Sep'] }, { meses: ['Oct', 'Nov'] }];

test('temporadaDeMes: encuentra la fila de cada mes, en es y en en', () => {
  const esperado = [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 0]; // enero (0) a diciembre (11)
  for (const filas of [es, en]) {
    for (let mes = 0; mes < 12; mes++) assert.equal(t.temporadaDeMes(filas, mes), esperado[mes], `mes ${mes}`);
  }
});

test('temporadaDeMes: sin fila para el mes, -1', () => {
  assert.equal(t.temporadaDeMes([{ meses: ['Abr', 'May'] }], 0), -1);
  assert.equal(t.temporadaDeMes([], 3), -1);
  assert.equal(t.temporadaDeMes([{ meses: ['???'] }], 3), -1);
});
