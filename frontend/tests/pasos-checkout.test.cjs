/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PASOS_CHECKOUT_TEST_OUT, 'lib/pasos-checkout.js'));

test('el orden de los pasos es viaje, contacto, detalles, pago', () => {
  assert.deepEqual([...p.ORDEN_PASOS], ['viaje', 'contacto', 'detalles', 'pago']);
});

test('numera los pasos de 1 a 4', () => {
  assert.equal(p.numeroDePaso('viaje'), 1);
  assert.equal(p.numeroDePaso('contacto'), 2);
  assert.equal(p.numeroDePaso('detalles'), 3);
  assert.equal(p.numeroDePaso('pago'), 4);
});

test('el paso actual está activo, los anteriores completados y los siguientes ocultos', () => {
  assert.equal(p.estadoDeTarjeta('viaje', 'contacto', null), 'completado');
  assert.equal(p.estadoDeTarjeta('contacto', 'contacto', null), 'activo');
  assert.equal(p.estadoDeTarjeta('detalles', 'contacto', null), 'oculto');
  assert.equal(p.estadoDeTarjeta('pago', 'contacto', null), 'oculto');
});

test('un paso ya confirmado reabierto a mano queda en edición', () => {
  assert.equal(p.estadoDeTarjeta('viaje', 'detalles', 'viaje'), 'editando');
  assert.equal(p.estadoDeTarjeta('contacto', 'detalles', 'viaje'), 'completado');
});

test('editar el paso activo no cambia su estado', () => {
  assert.equal(p.estadoDeTarjeta('contacto', 'contacto', 'contacto'), 'activo');
});

test('en el pago todas las tarjetas de pasos están completadas', () => {
  for (const id of ['viaje', 'contacto', 'detalles']) {
    assert.equal(p.estadoDeTarjeta(id, 'pago', null), 'completado');
  }
});
