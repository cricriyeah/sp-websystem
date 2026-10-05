/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const calendario = require(path.join(process.env.CALENDARIO_SEMANA_TEST_OUT, 'lib/calendario-semana.js'));

test('sin fecha elegida, muestra la semana del primer dia reservable sin marcar un dia', () => {
  assert.deepEqual(calendario.semanaVisible(null, '2026-10-02'), {
    inicio: '2026-09-28',
    dias: ['2026-09-28', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'],
    seleccionado: null,
  });
});

test('una fecha elegida ancla su semana incluso al cruzar de año', () => {
  assert.deepEqual(calendario.semanaVisible('2027-01-01', '2026-10-02'), {
    inicio: '2026-12-28',
    dias: ['2026-12-28', '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01', '2027-01-02', '2027-01-03'],
    seleccionado: '2027-01-01',
  });
});

test('no permite retroceder a una semana anterior a la primera reservable', () => {
  assert.equal(calendario.puedeRetroceder('2026-09-28', '2026-10-02'), false);
  assert.equal(calendario.puedeRetroceder('2026-10-05', '2026-10-02'), true);
});

test('si cambia el minimo de regreso, deja de mostrar una seleccion anterior', () => {
  assert.deepEqual(calendario.semanaVisible('2026-10-04', '2026-10-10'), {
    inicio: '2026-10-05',
    dias: ['2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09', '2026-10-10', '2026-10-11'],
    seleccionado: null,
  });
});
