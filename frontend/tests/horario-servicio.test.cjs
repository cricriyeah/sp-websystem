/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const h = require(path.join(process.env.HORARIO_TEST_OUT, 'lib/horario-servicio.js'));
const d = require(path.join(process.env.HORARIO_TEST_OUT, 'lib/dates.js'));

const servicio = (over = {}) => ({
  pide_hora: true, hora_apertura: '05:00:00', hora_cierre: '07:00:00', paso_hora_minutos: 30, ...over,
});

test('las horas salen del rango y del paso del servicio', () => {
  assert.deepEqual(h.horasDeServicio(servicio()), ['05:00', '05:30', '06:00', '06:30', '07:00']);
  assert.deepEqual(h.horasDeServicio(servicio({ paso_hora_minutos: 60 })), ['05:00', '06:00', '07:00']);
});

test('un servicio que no pide hora no ofrece ninguna', () => {
  assert.deepEqual(h.horasDeServicio(servicio({ pide_hora: false })), []);
});

test('sin rango no se inventa uno', () => {
  assert.deepEqual(h.horasDeServicio(servicio({ hora_apertura: null, hora_cierre: null })), []);
});

test('un paquete usa las horas de su actividad principal y respeta pide_hora', () => {
  const principal = { orden: 2, servicio: { estrategia_cupo: 'por_recurso_dia', ...servicio({ paso_hora_minutos: 60 }) } };
  const otro = { orden: 1, servicio: { estrategia_cupo: 'bajo_demanda', ...servicio({ pide_hora: false }) } };
  const paquete = { pide_hora: true, servicios_asociados: [otro, principal] };
  assert.deepEqual(h.horasDePaquete(paquete), ['05:00', '06:00', '07:00']);
  assert.deepEqual(h.horasDePaquete({ ...paquete, pide_hora: false }), []);
});

test('el calendario de la reserva ya no valida la hora contra una lista fija', () => {
  const get = (k) => ({ time: '08:30' })[k];
  assert.equal(d.parseBookingQuery(get, '2026-01-01').time, '08:30');
  assert.equal(d.parseBookingQuery((k) => ({ time: 'abc' })[k], '2026-01-01').time, undefined);
});
