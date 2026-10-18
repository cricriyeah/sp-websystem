/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CAMPO_PASO_TEST_OUT, 'lib/campo-paso.js'));

test('los campos del viaje, los del contacto y la recogida, y lo demás', () => {
  for (const campo of ['numero_personas', 'hora', 'fecha', 'fecha_salida', 'fecha_regreso', 'tipo_traslado', 'personalizaciones']) {
    assert.equal(c.pasoDeCampo(campo), 'viaje', campo);
  }
  for (const campo of ['nombre_cliente', 'telefono_cliente', 'correo_cliente', 'punto_encuentro', 'direccion_personalizada', 'zona']) {
    assert.equal(c.pasoDeCampo(campo), 'datos', campo);
  }
  assert.equal(c.pasoDeCampo('deslinde_aceptado'), 'pago');
  assert.equal(c.pasoDeCampo('codigo_promocional'), 'pago');
});

test('un dato de contacto lleva al control por el id de su error', () => {
  assert.deepEqual(c.destinoDeError({ correo_cliente: ['inválido'] }, 'traslado'), { paso: 'datos', campo: 'traslado-error-email' });
  assert.deepEqual(c.destinoDeError({ telefono_cliente: ['x'] }, 'pedido'), { paso: 'datos', campo: 'pedido-error-phone' });
});

test('un campo sin control (la fecha) solo abre su paso', () => {
  assert.deepEqual(c.destinoDeError({ fecha: ['pasada'] }, 'checkout'), { paso: 'viaje', campo: '' });
  assert.deepEqual(c.destinoDeError({ zona: ['falta'] }, 'traslado'), { paso: 'datos', campo: '' });
});

test('con errores en dos pasos manda el primero del flujo', () => {
  assert.equal(c.destinoDeError({ nombre_cliente: ['x'], numero_personas: ['y'] }, 'checkout').paso, 'viaje');
});

test('lo que no es de un paso previo a Pago, o no es un objeto, no tiene destino', () => {
  assert.equal(c.destinoDeError({ deslinde_aceptado: ['x'] }, 'checkout'), null);
  assert.equal(c.destinoDeError(null, 'checkout'), null);
  assert.equal(c.destinoDeError([], 'checkout'), null);
  assert.equal(c.destinoDeError('error', 'checkout'), null);
});
