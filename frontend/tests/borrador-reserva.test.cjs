/* eslint-disable @typescript-eslint/no-require-imports */
const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const b = require(path.join(process.env.BORRADOR_TEST_OUT, 'lib/borrador-reserva.js'));

function falsoAlmacen() {
  const datos = new Map();
  return {
    getItem: (k) => (datos.has(k) ? datos.get(k) : null),
    setItem: (k, v) => { datos.set(k, String(v)); },
    removeItem: (k) => { datos.delete(k); },
  };
}

function instalar(almacen) {
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: almacen });
}

beforeEach(() => instalar(falsoAlmacen()));

test('la clave lleva ruta y producto', () => {
  assert.equal(b.claveBorrador('reservar', 'pesca'), 'salysol:borrador:reservar:pesca');
});

test('ida y vuelta', () => {
  b.guardarBorrador('k', { personas: 3, paso: 'datos' });
  assert.deepEqual(b.leerBorrador('k'), { personas: 3, paso: 'datos' });
});

test('sin nada guardado devuelve null', () => {
  assert.equal(b.leerBorrador('k'), null);
});

test('una versión distinta se descarta', () => {
  globalThis.sessionStorage.setItem('k', JSON.stringify({ version: 99, guardadoEn: Date.now(), datos: { a: 1 } }));
  assert.equal(b.leerBorrador('k'), null);
});

test('vence a las 4 horas', () => {
  b.guardarBorrador('k', { a: 1 }, 1000);
  assert.deepEqual(b.leerBorrador('k', 1000 + 4 * 3600 * 1000 - 1), { a: 1 });
  assert.equal(b.leerBorrador('k', 1000 + 4 * 3600 * 1000), null);
});

test('JSON roto devuelve null sin lanzar', () => {
  globalThis.sessionStorage.setItem('k', '{no es json');
  assert.equal(b.leerBorrador('k'), null);
});

test('borrar quita el borrador', () => {
  b.guardarBorrador('k', { a: 1 });
  b.borrarBorrador('k');
  assert.equal(b.leerBorrador('k'), null);
});

test('si el almacenamiento lanza, nada revienta', () => {
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, get() { throw new Error('bloqueado'); } });
  assert.doesNotThrow(() => b.guardarBorrador('k', { a: 1 }));
  assert.equal(b.leerBorrador('k'), null);
  assert.doesNotThrow(() => b.borrarBorrador('k'));
});
