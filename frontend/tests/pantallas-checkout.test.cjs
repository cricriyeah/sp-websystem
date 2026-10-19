/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PANTALLAS_CHECKOUT_TEST_OUT, 'lib/pantallas-checkout.js'));

const ids = (pantallas) => pantallas.map((x) => x.id);

test('servicio suelto: fecha, extras, datos, cómo pagas y tarjeta', () => {
  const pantallas = p.pantallasDe({ tipo: 'servicio', tieneExtras: true });
  assert.deepEqual(ids(pantallas), ['viaje', 'extras', 'contacto', 'como-pagas', 'tarjeta-0']);
});

test('servicio suelto sin extras omite esa pantalla', () => {
  const pantallas = p.pantallasDe({ tipo: 'servicio', tieneExtras: false });
  assert.deepEqual(ids(pantallas), ['viaje', 'contacto', 'como-pagas', 'tarjeta-0']);
});

test('paquete: una pantalla por servicio y recogida solo con traslado', () => {
  const conTraslado = p.pantallasDe({ tipo: 'paquete', servicios: 3, conTraslado: true, empresas: 1 });
  assert.deepEqual(ids(conTraslado), [
    'inicio', 'servicio-0', 'servicio-1', 'servicio-2', 'contacto', 'recogida', 'como-pagas', 'tarjeta-0',
  ]);
  const sinTraslado = p.pantallasDe({ tipo: 'paquete', servicios: 2, conTraslado: false, empresas: 1 });
  assert.deepEqual(ids(sinTraslado), ['inicio', 'servicio-0', 'servicio-1', 'contacto', 'como-pagas', 'tarjeta-0']);
});

test('cruza-empresa: una pantalla de tarjeta por empresa', () => {
  const pantallas = p.pantallasDe({ tipo: 'paquete', servicios: 2, conTraslado: false, empresas: 2 });
  assert.deepEqual(ids(pantallas).slice(-3), ['como-pagas', 'tarjeta-0', 'tarjeta-1']);
  const tarjetas = pantallas.filter((x) => x.tipo === 'tarjeta');
  assert.deepEqual(tarjetas.map((x) => x.indice), [0, 1]);
});

test('traslado: tipo, fecha, hora y pasajeros, datos, recogida, pago', () => {
  const pantallas = p.pantallasDe({ tipo: 'traslado' });
  assert.deepEqual(ids(pantallas), [
    'tipo', 'fecha', 'hora-pasajeros', 'contacto', 'recogida', 'como-pagas', 'tarjeta-0',
  ]);
});

test('cada pantalla cae en uno de los tres pasos, en orden', () => {
  const pantallas = p.pantallasDe({ tipo: 'paquete', servicios: 2, conTraslado: true, empresas: 2 });
  const pasos = pantallas.map((x) => x.paso);
  assert.deepEqual(pasos, ['viaje', 'viaje', 'viaje', 'datos', 'datos', 'pago', 'pago', 'pago']);
  assert.equal(p.pasoDeLaPantalla(pantallas, 'recogida'), 'datos');
  assert.equal(p.pasoDeLaPantalla(pantallas, 'tarjeta-1'), 'pago');
});

test('siguiente y anterior se mueven de una en una', () => {
  const pantallas = p.pantallasDe({ tipo: 'paquete', servicios: 2, conTraslado: false, empresas: 1 });
  assert.equal(p.siguiente(pantallas, 'servicio-0'), 'servicio-1');
  assert.equal(p.anterior(pantallas, 'servicio-1'), 'servicio-0');
  // Desde Tus datos, atrás cae en el último servicio, no en el primero del paso.
  assert.equal(p.anterior(pantallas, 'contacto'), 'servicio-1');
});

test('en los extremos no hay pantalla: la primera sale al origen, la última cobra', () => {
  const pantallas = p.pantallasDe({ tipo: 'servicio', tieneExtras: false });
  assert.equal(p.anterior(pantallas, 'viaje'), null);
  assert.equal(p.siguiente(pantallas, 'tarjeta-0'), null);
});

test('una pantalla que ya no existe se reemplaza por una válida', () => {
  const pantallas = p.pantallasDe({ tipo: 'servicio', tieneExtras: false });
  // El servicio dejó de tener extras: la URL vieja apunta a una pantalla que ya no está.
  assert.equal(p.pantallaValida(pantallas, 'extras'), 'viaje');
  assert.equal(p.pantallaValida(pantallas, null), 'viaje');
  assert.equal(p.pantallaValida(pantallas, 'contacto'), 'contacto');
});

test('primera pantalla de un paso, para entrar desde ?paso=', () => {
  const pantallas = p.pantallasDe({ tipo: 'traslado' });
  assert.equal(p.primeraDelPaso(pantallas, 'viaje'), 'tipo');
  assert.equal(p.primeraDelPaso(pantallas, 'datos'), 'contacto');
  assert.equal(p.primeraDelPaso(pantallas, 'pago'), 'como-pagas');
});

test('pantallas anteriores a otra, para saber si ya se pasó por ella', () => {
  const pantallas = p.pantallasDe({ tipo: 'traslado' });
  assert.equal(p.estaAntesDe(pantallas, 'fecha', 'contacto'), true);
  assert.equal(p.estaAntesDe(pantallas, 'contacto', 'fecha'), false);
  assert.equal(p.estaAntesDe(pantallas, 'fecha', 'fecha'), false);
});
