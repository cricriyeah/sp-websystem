/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PASO_URL_TEST_OUT, 'lib/paso-url.js'));

test('pasoDeQuery acepta solo los tres pasos', () => {
  assert.equal(p.pasoDeQuery('datos'), 'datos');
  assert.equal(p.pasoDeQuery('contacto'), null);
  assert.equal(p.pasoDeQuery(null), null);
});

test('un paso al que no se ha llegado se redirige al último válido', () => {
  assert.deepEqual(p.decidirPaso('pago', 'viaje', false), { tipo: 'redirigir', a: 'viaje' });
  assert.deepEqual(p.decidirPaso('datos', 'viaje', false), { tipo: 'redirigir', a: 'viaje' });
});

test('el paso actual no deja nada reabierto; sin ?paso= vale viaje', () => {
  assert.deepEqual(p.decidirPaso('datos', 'datos', false), { tipo: 'cerrarEdicion' });
  assert.deepEqual(p.decidirPaso(null, 'viaje', false), { tipo: 'cerrarEdicion' });
});

test('Atrás a un paso anterior lo reabre', () => {
  assert.deepEqual(p.decidirPaso('viaje', 'pago', false), { tipo: 'editar', paso: 'viaje' });
  assert.deepEqual(p.decidirPaso(null, 'datos', false), { tipo: 'editar', paso: 'viaje' });
});

test('con un pago en curso Atrás no reabre nada: vuelve a pago', () => {
  assert.deepEqual(p.decidirPaso('datos', 'pago', true), { tipo: 'redirigir', a: 'pago' });
});

test('conPaso conserva el resto del query', () => {
  assert.equal(p.conPaso('?moneda=USD&origen=sede', 'datos'), '?moneda=USD&origen=sede&paso=datos');
  assert.equal(p.conPaso('?paso=viaje&moneda=MXN', 'pago'), '?paso=pago&moneda=MXN');
  assert.equal(p.conPaso('', 'viaje'), '?paso=viaje');
});

// Asistente móvil: la pantalla viaja junto al paso (`?paso=datos&pantalla=recogida`).
const pc = require(path.join(process.env.PASO_URL_TEST_OUT, 'lib/pantallas-checkout.js'));
const traslado = pc.pantallasDe({ tipo: 'traslado' });

test('conPantalla escribe el paso de la pantalla y conserva el resto del query', () => {
  const query = new URLSearchParams(p.conPantalla('?moneda=usd&paso=viaje', traslado, 'recogida'));
  assert.equal(query.get('paso'), 'datos');
  assert.equal(query.get('pantalla'), 'recogida');
  assert.equal(query.get('moneda'), 'usd');
});

test('una pantalla ya alcanzada se muestra tal cual', () => {
  assert.deepEqual(p.decidirPantalla('fecha', traslado, 'contacto', null), { tipo: 'mostrar', id: 'fecha' });
  assert.deepEqual(p.decidirPantalla('contacto', traslado, 'contacto', null), { tipo: 'mostrar', id: 'contacto' });
});

test('una pantalla a la que no se ha llegado se reescribe a la más avanzada', () => {
  assert.deepEqual(p.decidirPantalla('como-pagas', traslado, 'fecha', null), { tipo: 'redirigir', a: 'fecha' });
});

test('una pantalla que no existe en la ruta se reescribe a la más avanzada', () => {
  assert.deepEqual(p.decidirPantalla('extras', traslado, 'fecha', null), { tipo: 'redirigir', a: 'fecha' });
});

test('sin ?pantalla= manda el estado', () => {
  assert.deepEqual(p.decidirPantalla(null, traslado, 'fecha', null), { tipo: 'nada' });
});

test('con un pago en curso no se vuelve antes de la pantalla mínima', () => {
  assert.deepEqual(
    p.decidirPantalla('contacto', traslado, 'tarjeta-0', 'tarjeta-0'),
    { tipo: 'redirigir', a: 'tarjeta-0' },
  );
});
