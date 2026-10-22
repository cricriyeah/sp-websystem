/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const a = require(path.join(process.env.ANTICIPACION_TEST_OUT, 'lib/anticipacion.js'));

// 11:00 pm del 9 de octubre en la sede (UTC-7) = 06:00 UTC del 10.
const AHORA = new Date('2026-10-10T06:00:00Z');

test('el día de la sede no es el del UTC', () => {
  assert.equal(a.hoyEnSede(AHORA), '2026-10-09');
});

test('a las 11 pm no se reserva la salida de las 7 am del día siguiente', () => {
  assert.equal(a.cumpleAnticipacion('2026-10-10', '07:00', AHORA, 16), false);
});

test('16 horas justas cumplen y un minuto menos no', () => {
  assert.equal(a.cumpleAnticipacion('2026-10-10', '15:00', AHORA, 16), true);
  assert.equal(a.cumpleAnticipacion('2026-10-10', '14:59', AHORA, 16), false);
});

test('de las horas del servicio solo quedan las que cumplen ese día', () => {
  const horas = ['07:00', '08:00', '15:00', '16:00'];
  assert.deepEqual(a.horasConAnticipacion('2026-10-10', horas, AHORA, 16), ['15:00', '16:00']);
  assert.deepEqual(a.horasConAnticipacion('2026-10-11', horas, AHORA, 16), horas);
});

test('primera fecha: sin horas, mañana; con horas, la primera donde cabe la última', () => {
  assert.equal(a.fechaMinimaReservable([], AHORA, 16), '2026-10-10');
  // Ventana de 7 a 8: la última (8:00 am) del 10 queda a 9 h, del 11 a 33 h: el 11 es la primera.
  assert.equal(a.fechaMinimaReservable(['07:00', '08:00'], AHORA, 16), '2026-10-11');
  // Una ventana que llega a las 10 pm sí cabe mañana.
  assert.equal(a.fechaMinimaReservable(['06:00', '22:00'], AHORA, 16), '2026-10-10');
});

test('con 0 horas la regla está apagada', () => {
  assert.equal(a.cumpleAnticipacion('2020-01-01', '07:00', AHORA, 0), true);
});
