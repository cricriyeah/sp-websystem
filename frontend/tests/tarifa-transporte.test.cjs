/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const t = require(path.join(process.env.TARIFA_TEST_OUT, 'lib/tarifa-transporte.js'));

const T = (over) => ({
  tipo_traslado: 'redondo_aeropuerto', zona: '', personas_min: 1, personas_max: null,
  precio: '4500.00', ...over,
});

test('elige por tipo, zona y rango de personas', () => {
  const tarifas = [
    T({ personas_max: 4, precio: '4500.00' }),
    T({ personas_min: 5, precio: '6000.00' }),
    T({ tipo_traslado: 'redondo_actividad', zona: 'centro', precio: '1500.00' }),
  ];
  assert.equal(t.resolverTarifa(tarifas, 'redondo_aeropuerto', '', 4).precio, '4500.00');
  assert.equal(t.resolverTarifa(tarifas, 'redondo_aeropuerto', '', 5).precio, '6000.00');
  assert.equal(t.resolverTarifa(tarifas, 'redondo_actividad', 'centro', 2).precio, '1500.00');
  assert.equal(t.resolverTarifa(tarifas, 'redondo_actividad', 'periferia', 2), null);
});

test('tarifa USD derivada del tipo de cambio', () => {
  assert.equal(t.precioTarifa(T({}), 'MXN', '18.0000'), 4500);
  assert.equal(t.precioTarifa(T({}), 'USD', '18.0000'), 250);
  assert.equal(t.precioTarifa(T({ precio: '1500.00' }), 'USD', '18.0000'), 84);
});
