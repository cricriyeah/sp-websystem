/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CALENDARIO_MES_TEST_OUT, 'lib/calendario-mes.js'));

test('el mes siempre son 6 semanas de lunes a domingo', () => {
  // Noviembre de 2026 empieza en domingo: 6 huecos antes del día 1.
  const celdas = c.celdasDelMes('2026-11-01');
  assert.equal(celdas.length, 42);
  assert.deepEqual(celdas.slice(0, 7), [null, null, null, null, null, null, '2026-11-01']);
  assert.equal(celdas[35], '2026-11-30');
  assert.ok(celdas.slice(36).every((x) => x === null));
  // Febrero de 2027 empieza en lunes y cabe en 4 semanas: igual son 42 celdas.
  assert.equal(c.celdasDelMes('2027-02-01').length, 42);
  assert.equal(c.celdasDelMes('2027-02-01')[0], '2027-02-01');
});

test('mover de mes', () => {
  assert.equal(c.moverMes('2026-12-01', 1), '2027-01-01');
  assert.equal(c.moverMes('2026-01-01', -1), '2025-12-01');
  assert.equal(c.inicioDeMes('2026-11-17'), '2026-11-01');
});

const base = { minDate: '2026-11-03', hoy: '2026-11-02', sinCupo: {}, desde: null, hasta: null, banda: [] };

test('antes del mínimo no se reserva; el día sin cupo se marca aparte', () => {
  assert.equal(c.estadoDeCelda('2026-11-02', base).base, 'no_reservable');
  assert.equal(c.estadoDeCelda('2026-11-02', base).hoy, true);
  assert.equal(c.estadoDeCelda('2026-11-05', base).base, 'disponible');
  assert.equal(c.estadoDeCelda('2026-11-05', { ...base, sinCupo: { '2026-11-05': 'lleno' } }).base, 'sin_cupo');
});

test('selección, rango firme con extremos y banda de vista previa', () => {
  const unico = { ...base, desde: '2026-11-05' };
  assert.equal(c.estadoDeCelda('2026-11-05', unico).marca, 'seleccion');
  const rango = { ...base, desde: '2026-11-05', hasta: '2026-11-08' };
  assert.equal(c.estadoDeCelda('2026-11-05', rango).marca, 'extremo');
  assert.equal(c.estadoDeCelda('2026-11-06', rango).marca, 'rango');
  assert.equal(c.estadoDeCelda('2026-11-08', rango).marca, 'extremo');
  assert.equal(c.estadoDeCelda('2026-11-05', rango).inicioBanda, true);
  assert.equal(c.estadoDeCelda('2026-11-08', rango).finBanda, true);
  assert.equal(c.estadoDeCelda('2026-11-09', rango).marca, 'ninguna');
  // Eligiendo de nuevo, la vista previa tapa el rango anterior.
  const eligiendo = { ...rango, banda: ['2026-11-20'] };
  assert.equal(c.estadoDeCelda('2026-11-06', eligiendo).marca, 'ninguna');
  const previa = { ...base, banda: ['2026-11-10', '2026-11-11', '2026-11-12'] };
  assert.equal(c.estadoDeCelda('2026-11-11', previa).marca, 'vista_previa');
  assert.equal(c.estadoDeCelda('2026-11-10', previa).inicioBanda, true);
  assert.equal(c.estadoDeCelda('2026-11-12', previa).finBanda, true);
});

test('rango fijo: la vista previa del cursor no esconde la estancia ya elegida', () => {
  // Paquete de 3 noches elegido del 5 al 8; el cursor pasa por el 20 y dibuja su vista previa.
  const elegido = { ...base, desde: '2026-11-05', hasta: '2026-11-08', banda: ['2026-11-20', '2026-11-21', '2026-11-22', '2026-11-23'], conservarSeleccion: true };
  assert.equal(c.estadoDeCelda('2026-11-05', elegido).marca, 'extremo');
  assert.equal(c.estadoDeCelda('2026-11-06', elegido).marca, 'rango');
  assert.equal(c.estadoDeCelda('2026-11-08', elegido).finBanda, true);
  assert.equal(c.estadoDeCelda('2026-11-21', elegido).marca, 'vista_previa');
  // Donde la vista previa cae sobre la estancia elegida, se ve la vista previa.
  const encima = { ...elegido, banda: ['2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09'] };
  assert.equal(c.estadoDeCelda('2026-11-07', encima).marca, 'vista_previa');
  assert.equal(c.estadoDeCelda('2026-11-05', encima).marca, 'extremo');
});

test('fecha única: un toque elige', () => {
  assert.deepEqual(c.alTocar('fecha_unica', null, '2026-11-05', null), { seleccion: { desde: '2026-11-05', hasta: null }, previa: null });
});

test('paquete con noches: un toque elige la llegada y la salida sale de las noches', () => {
  assert.deepEqual(c.alTocar('rango_fijo_paquete', null, '2026-11-05', 3), { seleccion: { desde: '2026-11-05', hasta: '2026-11-08' }, previa: null });
  // Tocar otro día lo elige también: no hay vista previa que confirmar.
  assert.deepEqual(c.alTocar('rango_fijo_paquete', '2026-11-05', '2026-11-06', 3), { seleccion: { desde: '2026-11-06', hasta: '2026-11-09' }, previa: null });
  // Cruza el fin de mes: la salida cae en el mes siguiente.
  assert.deepEqual(c.alTocar('rango_fijo_paquete', null, '2026-10-30', 5), { seleccion: { desde: '2026-10-30', hasta: '2026-11-04' }, previa: null });
});

test('llegada y salida (o ida y regreso): el primer toque fija el inicio y el segundo, posterior, cierra', () => {
  for (const control of ['rango_llegada_salida', 'ida_y_regreso']) {
    assert.deepEqual(c.alTocar(control, null, '2026-11-05', null), { previa: '2026-11-05' }, control);
    assert.deepEqual(
      c.alTocar(control, '2026-11-05', '2026-11-09', null),
      { seleccion: { desde: '2026-11-05', hasta: '2026-11-09' }, previa: null },
      control,
    );
    // Un día igual o anterior al inicio lo reemplaza.
    assert.deepEqual(c.alTocar(control, '2026-11-05', '2026-11-03', null), { previa: '2026-11-03' }, control);
  }
});

test('banda de vista previa según el control', () => {
  assert.deepEqual(c.bandaPrevia('rango_fijo_paquete', '2026-11-05', null, 2), ['2026-11-05', '2026-11-06', '2026-11-07']);
  assert.deepEqual(c.bandaPrevia('rango_llegada_salida', '2026-11-05', '2026-11-07', null), ['2026-11-05', '2026-11-06', '2026-11-07']);
  assert.deepEqual(c.bandaPrevia('rango_llegada_salida', '2026-11-05', null, null), ['2026-11-05']);
  assert.deepEqual(c.bandaPrevia('rango_llegada_salida', '2026-11-05', '2026-11-04', null), ['2026-11-05']);
  assert.deepEqual(c.bandaPrevia('fecha_unica', '2026-11-05', null, null), []);
  assert.deepEqual(c.bandaPrevia('rango_fijo_paquete', null, null, 2), []);
});

test('atajos relativos a hoy: mañana y en 2 días, deshabilitados antes del mínimo', () => {
  assert.deepEqual(c.atajos('2026-11-02', '2026-11-03'), [
    { clave: 'manana', fecha: '2026-11-03', antesDelMinimo: false },
    { clave: 'en2', fecha: '2026-11-04', antesDelMinimo: false },
  ]);
  assert.deepEqual(c.atajos('2026-11-02', '2026-11-04').map((a) => a.antesDelMinimo), [true, false]);
});

test('teclado: flechas, semana, mes, inicio y fin de semana', () => {
  assert.equal(c.moverFoco('2026-11-05', 'ArrowRight'), '2026-11-06');
  assert.equal(c.moverFoco('2026-11-05', 'ArrowLeft'), '2026-11-04');
  assert.equal(c.moverFoco('2026-11-05', 'ArrowDown'), '2026-11-12');
  assert.equal(c.moverFoco('2026-11-05', 'ArrowUp'), '2026-10-29');
  assert.equal(c.moverFoco('2026-11-05', 'PageDown'), '2026-12-05');
  assert.equal(c.moverFoco('2026-01-31', 'PageDown'), '2026-02-28');
  // 2026-11-05 es jueves: Inicio va al lunes, Fin al domingo.
  assert.equal(c.moverFoco('2026-11-05', 'Home'), '2026-11-02');
  assert.equal(c.moverFoco('2026-11-05', 'End'), '2026-11-08');
  assert.equal(c.moverFoco('2026-11-05', 'Enter'), null);
});
