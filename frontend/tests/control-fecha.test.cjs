/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CONTROL_FECHA_TEST_OUT, 'lib/control-fecha.js'));

const servicio = (estrategia_cupo, pide_hora = true) => ({ tipo: 'servicio', estrategia_cupo, pide_hora });

test('pesca (una panga por día): fecha única con hora', () => {
  assert.deepEqual(c.controlDeFecha(servicio('por_recurso_dia')), { control: 'fecha_unica', pideHora: true });
});

test('paseo o tour por cupo de personas: fecha única', () => {
  assert.deepEqual(c.controlDeFecha(servicio('por_cupo')), { control: 'fecha_unica', pideHora: true });
});

test('hospedaje por noche suelto: rango de llegada y salida, sin hora', () => {
  assert.deepEqual(c.controlDeFecha(servicio('por_noche', false)), { control: 'rango_llegada_salida', pideHora: false });
});

test('bajo demanda: fecha única y la hora solo si el servicio la pide', () => {
  assert.deepEqual(c.controlDeFecha(servicio('bajo_demanda', false)), { control: 'fecha_unica', pideHora: false });
});

test('traslados: solo el redondo con aeropuerto pide ida y regreso; todos piden hora', () => {
  assert.deepEqual(c.controlDeFecha({ tipo: 'traslado', tipoTraslado: 'redondo_aeropuerto' }), { control: 'ida_y_regreso', pideHora: true });
  assert.deepEqual(c.controlDeFecha({ tipo: 'traslado', tipoTraslado: 'redondo_actividad' }), { control: 'fecha_unica', pideHora: true });
  assert.deepEqual(c.controlDeFecha({ tipo: 'traslado', tipoTraslado: 'recepcion_aeropuerto' }), { control: 'fecha_unica', pideHora: true });
});

test('paquete con noches fijas (una empresa o cruza-empresa): rango fijo desde la llegada', () => {
  assert.deepEqual(c.controlDeFecha({ tipo: 'paquete', noches: 3, pide_hora: false }), { control: 'rango_fijo_paquete', pideHora: false });
});

test('paquete sin hospedaje: fecha única de inicio', () => {
  assert.deepEqual(c.controlDeFecha({ tipo: 'paquete', noches: null, pide_hora: true }), { control: 'fecha_unica', pideHora: true });
  assert.deepEqual(c.controlDeFecha({ tipo: 'paquete', noches: 0, pide_hora: true }), { control: 'fecha_unica', pideHora: true });
});

test('dos toques solo cuando hay dos extremos que elegir: llegada y salida, ida y regreso', () => {
  for (const control of ['fecha_unica', 'rango_fijo_paquete']) {
    assert.equal(c.pideDosToques(control), false, control);
  }
  for (const control of ['rango_llegada_salida', 'ida_y_regreso']) {
    assert.equal(c.pideDosToques(control), true, control);
  }
});
