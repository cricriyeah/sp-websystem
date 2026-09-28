/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CALENDARIO_TEST_OUT, 'lib/calendario-paquete.js'));

const PESCA_DIA_2 = { dia_estancia: 2, estrategia_cupo: 'por_recurso_dia', noches: null };
const HOTEL_3 = { dia_estancia: 1, estrategia_cupo: 'por_noche', noches: 3 };
const INICIO = '2026-10-10';

test('suma días cruzando de mes', () => {
  assert.equal(c.sumarDias('2026-10-30', 3), '2026-11-02');
});

test('noches del paquete salen del hospedaje', () => {
  assert.equal(c.nochesDelPaquete([PESCA_DIA_2, HOTEL_3]), 3);
  assert.equal(c.nochesDelPaquete([PESCA_DIA_2]), null);
});

test('la fecha de cada componente cuenta desde el día 1', () => {
  assert.equal(c.fechaDeComponente(INICIO, 1), '2026-10-10');
  assert.equal(c.fechaDeComponente(INICIO, 2), '2026-10-11');
});

test('la salida es inicio + noches; sin hospedaje no hay salida', () => {
  assert.equal(c.fechaSalida(INICIO, [PESCA_DIA_2, HOTEL_3]), '2026-10-13');
  assert.equal(c.fechaSalida(INICIO, [PESCA_DIA_2]), null);
});
