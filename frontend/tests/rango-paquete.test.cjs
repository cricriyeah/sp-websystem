/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const r = require(path.join(process.env.RANGO_PAQUETE_TEST_OUT, 'lib/rango-paquete.js'));

test('N noches: de la llegada a la salida, y las noches que se duermen', () => {
  const rango = r.rangoDelPaquete('2026-10-30', 3);
  assert.equal(rango.llegada, '2026-10-30');
  assert.equal(rango.salida, '2026-11-02');
  assert.deepEqual(rango.noches, ['2026-10-30', '2026-10-31', '2026-11-01']);
  assert.deepEqual(rango.dias, ['2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02']);
});

test('0 noches o sin noches: un solo día', () => {
  for (const noches of [0, null]) {
    const rango = r.rangoDelPaquete('2026-10-30', noches);
    assert.equal(rango.salida, '2026-10-30', String(noches));
    assert.deepEqual(rango.dias, ['2026-10-30'], String(noches));
    assert.deepEqual(rango.noches, ['2026-10-30'], String(noches));
  }
});

test('marca solo los días que el cupo ya declara llenos', () => {
  const rango = r.rangoDelPaquete('2026-10-30', 3);
  const disponibilidad = { '2026-10-30': null, '2026-10-31': 'lleno', '2026-11-01': null, '2026-11-02': 'lleno' };
  // El día de salida no se duerme ahí: no cuenta aunque esté lleno.
  assert.deepEqual(r.diasSinCupoEnRango(rango, disponibilidad), ['2026-10-31']);
});

test('todo null o sin datos: ningún día sin cupo', () => {
  const rango = r.rangoDelPaquete('2026-10-30', 2);
  assert.deepEqual(r.diasSinCupoEnRango(rango, { '2026-10-30': null, '2026-10-31': null }), []);
  assert.deepEqual(r.diasSinCupoEnRango(rango, {}), []);
});

test('un solo día lleno', () => {
  const rango = r.rangoDelPaquete('2026-10-30', null);
  assert.deepEqual(r.diasSinCupoEnRango(rango, { '2026-10-30': 'sin_panga' }), ['2026-10-30']);
});
