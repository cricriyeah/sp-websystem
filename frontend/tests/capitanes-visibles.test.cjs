/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { capitanesVisibles, mostrarPendientesEnEsteEntorno } = require(path.join(process.env.CAPITANES_TEST_OUT, 'lib/capitanes-visibles.js'));

const lista = [{ nombre: 'Real' }, { nombre: 'Relleno', pendiente: true }, { nombre: 'Otro real', foto: '/x.webp' }];

test('en producción el relleno no se pinta', () => {
  assert.deepEqual(capitanesVisibles(lista, false).map((c) => c.nombre), ['Real', 'Otro real']);
});

test('fuera de producción se ven todos, relleno incluido', () => {
  assert.equal(capitanesVisibles(lista, true).length, 3);
});

test('si todos son relleno y es producción no queda ninguno (el bloque se omite)', () => {
  assert.deepEqual(capitanesVisibles([{ nombre: 'A', pendiente: true }, { nombre: 'B', pendiente: true }], false), []);
});

test('el entorno: producción lo oculta, desarrollo y la bandera lo muestran', () => {
  assert.equal(mostrarPendientesEnEsteEntorno({ NODE_ENV: 'production' }), false);
  assert.equal(mostrarPendientesEnEsteEntorno({ NODE_ENV: 'development' }), true);
  assert.equal(mostrarPendientesEnEsteEntorno({ NODE_ENV: 'production', NEXT_PUBLIC_VER_PENDIENTES: '1' }), true);
  assert.equal(mostrarPendientesEnEsteEntorno({ NODE_ENV: 'production', NEXT_PUBLIC_VER_PENDIENTES: '0' }), false);
});

test('no muta la lista original', () => {
  const copia = JSON.stringify(lista);
  capitanesVisibles(lista, false);
  assert.equal(JSON.stringify(lista), copia);
});
