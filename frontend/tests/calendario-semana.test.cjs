/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const calendario = require(path.join(process.env.CALENDARIO_SEMANA_TEST_OUT, 'lib/calendario-semana.js'));

test('sin fecha elegida, la ventana arranca en el primer dia reservable sin marcar un dia', () => {
  assert.deepEqual(calendario.semanaVisible(null, '2026-10-02'), {
    inicio: '2026-10-02',
    dias: ['2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'],
    seleccionado: null,
  });
});

test('nunca hay dias anteriores al minimo dentro de la ventana', () => {
  const { dias } = calendario.semanaVisible(null, '2026-10-02');
  assert.ok(dias.every((dia) => dia >= '2026-10-02'));
});

test('una fecha elegida ancla su ventana de 7 dias contados desde el minimo', () => {
  assert.deepEqual(calendario.semanaVisible('2026-10-10', '2026-10-02'), {
    inicio: '2026-10-09',
    dias: ['2026-10-09', '2026-10-10', '2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15'],
    seleccionado: '2026-10-10',
  });
});

test('la ventana cruza de año sin romperse', () => {
  assert.deepEqual(calendario.semanaVisible('2027-01-01', '2026-10-02'), {
    inicio: '2027-01-01',
    dias: ['2027-01-01', '2027-01-02', '2027-01-03', '2027-01-04', '2027-01-05', '2027-01-06', '2027-01-07'],
    seleccionado: '2027-01-01',
  });
});

test('el inicio de una ventana vuelve a dar la misma ventana', () => {
  const ventana = calendario.semanaVisible('2026-10-20', '2026-10-02');
  assert.equal(calendario.semanaVisible(ventana.inicio, '2026-10-02').inicio, ventana.inicio);
});

test('no permite retroceder antes del primer dia reservable', () => {
  assert.equal(calendario.puedeRetroceder('2026-10-02', '2026-10-02'), false);
  assert.equal(calendario.puedeRetroceder('2026-10-09', '2026-10-02'), true);
});

test('si cambia el minimo de regreso, deja de mostrar una seleccion anterior', () => {
  assert.deepEqual(calendario.semanaVisible('2026-10-04', '2026-10-10'), {
    inicio: '2026-10-10',
    dias: ['2026-10-10', '2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16'],
    seleccionado: null,
  });
});
