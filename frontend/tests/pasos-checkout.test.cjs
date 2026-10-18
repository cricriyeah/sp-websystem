/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PASOS_CHECKOUT_TEST_OUT, 'lib/pasos-checkout.js'));

test('el orden de los pasos es viaje, datos, pago', () => {
  assert.deepEqual([...p.ORDEN_PASOS], ['viaje', 'datos', 'pago']);
});

test('numera los pasos de 1 a 3', () => {
  assert.equal(p.numeroDePaso('viaje'), 1);
  assert.equal(p.numeroDePaso('datos'), 2);
  assert.equal(p.numeroDePaso('pago'), 3);
});

test('el paso actual está activo, los anteriores completados y los siguientes ocultos', () => {
  assert.equal(p.estadoDeTarjeta('viaje', 'datos', null), 'completado');
  assert.equal(p.estadoDeTarjeta('datos', 'datos', null), 'activo');
  assert.equal(p.estadoDeTarjeta('pago', 'datos', null), 'oculto');
});

test('un paso ya confirmado reabierto a mano queda en edición', () => {
  assert.equal(p.estadoDeTarjeta('viaje', 'pago', 'viaje'), 'editando');
  assert.equal(p.estadoDeTarjeta('datos', 'pago', 'viaje'), 'completado');
});

test('editar el paso activo no cambia su estado', () => {
  assert.equal(p.estadoDeTarjeta('datos', 'datos', 'datos'), 'activo');
});

test('en el pago todas las tarjetas de pasos están completadas', () => {
  for (const id of ['viaje', 'datos']) {
    assert.equal(p.estadoDeTarjeta(id, 'pago', null), 'completado');
  }
});

test('con una respuesta reabierta, la tarjeta activa se suspende', () => {
  assert.equal(p.estadoVisible('activo', true), 'suspendido');
  assert.equal(p.estadoVisible('activo', false), 'activo');
});

test('la suspensión no toca a las completadas ni a la que se está editando', () => {
  assert.equal(p.estadoVisible('completado', true), 'completado');
  assert.equal(p.estadoVisible('editando', true), 'editando');
});

test('dos completadas seguidas van pegadas; lo demás conserva su separación', () => {
  const estados = ['completado', 'completado', 'completado', 'activo'];
  assert.equal(p.unidaConAnterior(estados, 0), false);
  assert.equal(p.unidaConAnterior(estados, 1), true);
  assert.equal(p.unidaConAnterior(estados, 2), true);
  assert.equal(p.unidaConAnterior(estados, 3), false);
});

test('una tarjeta en edición o suspendida parte el bloque de completadas', () => {
  const estados = ['completado', 'editando', 'completado', 'suspendido'];
  assert.equal(p.unidaConAnterior(estados, 1), false);
  assert.equal(p.unidaConAnterior(estados, 2), false);
  assert.equal(p.unidaConAnterior(estados, 3), false);
});
