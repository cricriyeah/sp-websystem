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

test('con una respuesta reabierta, la tarjeta activa se suspende', () => {
  assert.equal(p.estadoVisible('activo', true), 'suspendido');
  assert.equal(p.estadoVisible('activo', false), 'activo');
});

test('la suspensión no toca a las completadas ni a la que se está editando', () => {
  assert.equal(p.estadoVisible('completado', true), 'completado');
  assert.equal(p.estadoVisible('editando', true), 'editando');
});

test('las completadas seguidas forman una sola lista y lo demás va aparte', () => {
  const items = [
    { id: 'viaje', estado: 'completado' },
    { id: 'contacto', estado: 'completado' },
    { id: 'pesca', estado: 'completado' },
    { id: 'traslado', estado: 'activo' },
  ];
  const segmentos = p.agruparResumenes(items);
  assert.equal(segmentos.length, 2);
  assert.equal(segmentos[0].tipo, 'resumen');
  assert.deepEqual(segmentos[0].items.map((i) => i.id), ['viaje', 'contacto', 'pesca']);
  assert.equal(segmentos[1].tipo, 'tarjeta');
  assert.equal(segmentos[1].item.id, 'traslado');
});

test('una tarjeta en edición parte la lista en dos y conserva el orden', () => {
  const items = [
    { id: 'viaje', estado: 'completado' },
    { id: 'contacto', estado: 'editando' },
    { id: 'pesca', estado: 'completado' },
    { id: 'traslado', estado: 'suspendido' },
  ];
  const segmentos = p.agruparResumenes(items);
  assert.deepEqual(segmentos.map((s) => s.tipo), ['resumen', 'tarjeta', 'resumen', 'tarjeta']);
  assert.equal(segmentos[1].item.id, 'contacto');
  assert.equal(segmentos[3].item.id, 'traslado');
});

test('sin completadas no hay lista de resumen', () => {
  const segmentos = p.agruparResumenes([{ id: 'viaje', estado: 'activo' }]);
  assert.deepEqual(segmentos.map((s) => s.tipo), ['tarjeta']);
});
