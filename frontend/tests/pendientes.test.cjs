/* eslint-disable @typescript-eslint/no-require-imports */
const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

globalThis.localStorage = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] ?? null,
    setItem: (key, value) => { store[key] = String(value); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();

const { guardarPendiente, listarPendientes, borrarPendiente } = require(
  path.join(process.env.PENDIENTES_TEST_OUT, 'lib/pendientes.js'),
);
const pendiente = (extra = {}) => ({
  tipo: 'reserva', checkoutId: 'a', empresaSlug: 'sal-y-sol',
  productoSlug: 'pesca', productoNombre: 'Pesca', ruta: '/es/reservar?servicio=pesca',
  actualizadoEn: new Date().toISOString(), ...extra,
});
beforeEach(() => localStorage.clear());

test('guarda, actualiza y borra por checkoutId', () => {
  guardarPendiente(pendiente());
  guardarPendiente(pendiente({ productoNombre: 'Pesca nueva' }));
  assert.deepEqual(listarPendientes().map((p) => p.productoNombre), ['Pesca nueva']);
  borrarPendiente('a');
  assert.deepEqual(listarPendientes(), []);
});

test('ordena y limita a tres, expulsando el más viejo sin dinero', () => {
  const now = Date.now();
  ['a', 'b', 'c', 'd'].forEach((id, i) => guardarPendiente(pendiente({
    checkoutId: id, actualizadoEn: new Date(now - (4 - i) * 60000).toISOString(),
    tieneDineroRetenido: id === 'a',
  })));
  assert.deepEqual(listarPendientes().map((p) => p.checkoutId), ['d', 'c', 'a']);
});

test('conserva los tres retenidos al entrar un cuarto', () => {
  const now = Date.now();
  ['a', 'b', 'c', 'd'].forEach((id, i) => guardarPendiente(pendiente({
    checkoutId: id, actualizadoEn: new Date(now - (4 - i) * 60000).toISOString(),
    tieneDineroRetenido: id !== 'd',
  })));
  assert.equal(listarPendientes().length, 4);
});

test('filtra vencidos y entradas mal formadas sin lanzar', () => {
  localStorage.setItem('salysol:pendientes:v1', JSON.stringify([
    null, {}, pendiente({ checkoutId: 'viejo', actualizadoEn: new Date(Date.now() - 8 * 86400000).toISOString() }),
    pendiente(),
  ]));
  assert.deepEqual(listarPendientes().map((p) => p.checkoutId), ['a']);
});

test('almacenamiento inaccesible no lanza', () => {
  const storage = globalThis.localStorage;
  globalThis.localStorage = { getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); } };
  try {
    assert.doesNotThrow(() => guardarPendiente(pendiente()));
    assert.deepEqual(listarPendientes(), []);
    assert.doesNotThrow(() => borrarPendiente('a'));
  } finally { globalThis.localStorage = storage; }
});
