/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.COLOR_ACTIVIDAD_TEST_OUT, 'lib/color-actividad.js'));

const servicio = (tipo_servicio) => ({ tipo_servicio });
const paquete = (...tipos) => ({ servicios_asociados: tipos.map((t) => ({ servicio: servicio(t) })) });

test('colorDeServicio: mar, traslado y estancia; lo desconocido es mar', () => {
  assert.equal(c.colorDeServicio(servicio('pesca')), 'mar');
  assert.equal(c.colorDeServicio(servicio('paseo')), 'mar');
  assert.equal(c.colorDeServicio(servicio('bajo_demanda')), 'mar');
  assert.equal(c.colorDeServicio(servicio('transporte')), 'traslado');
  assert.equal(c.colorDeServicio(servicio('hospedaje')), 'estancia');
  assert.equal(c.colorDeServicio(servicio('otro')), 'mar');
});

test('colorDePaquete: con hospedaje es estancia; con mar es mar; solo traslados es traslado', () => {
  assert.equal(c.colorDePaquete(paquete('pesca', 'hospedaje', 'transporte')), 'estancia');
  assert.equal(c.colorDePaquete(paquete('pesca', 'transporte')), 'mar');
  assert.equal(c.colorDePaquete(paquete('transporte')), 'traslado');
  assert.equal(c.colorDePaquete(paquete()), 'mar');
});
