/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PEDIDO_PAQUETE_TEST_OUT, 'lib/pedido-paquete.js'));

const check = (id, precio, precioUsd) => ({
  id, personalizacion_id: id, nombre: `extra-${id}`, tipo: 'amenidad', tipo_interaccion: 'check',
  opciones_seleccion: [], aviso_reforzado: false, cobrar_por_persona: false, cantidad_editable: false,
  precio, precio_usd: precioUsd, obligatorio: false, preseleccionado: false,
});

const servicio = (slug, empresa, tipo, extras) => ({
  id: 1, servicio_id: 1, orden: 1, dia_estancia: 1, noches: null, personas_incluidas: 3,
  servicio: { slug, empresa_slug: empresa, tipo_servicio: tipo, personalizaciones: extras },
});

const PAQUETE = {
  empresa_lider_slug: 'sal-y-sol', precio_ancla: '7500.00', precio_ancla_usd: '450.00',
  servicios_asociados: [
    servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00', '23.00')]),
    servicio('traslado', 'transportes-la-paz', 'transporte', [check(20, '150.00', '9.00')]),
  ],
};

const TARIFAS = {
  'transportes-la-paz': [
    { tipo_traslado: 'redondo_actividad', zona: 'centro', personas_min: 1, personas_max: null, precio: '1500.00', precio_usd: '90.00' },
  ],
};

const SELECCIONES = {
  pesca: { personas: 2, extras: [{ id: 10 }] },
  traslado: { personas: 2, extras: [{ id: 20 }], traslado: { tipo: 'redondo_actividad', zona: 'centro' } },
};

test('vector del spec en MXN: 6,400 + 1,650 = 8,050', () => {
  const r = p.calcularPedido(PAQUETE, SELECCIONES, 'MXN', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => [c.empresaSlug, c.monto]), [
    ['sal-y-sol', 6400],
    ['transportes-la-paz', 1650],
  ]);
  assert.equal(r.total, 8050);
});

test('vector en USD: 383 + 99 = 482', () => {
  const r = p.calcularPedido(PAQUETE, SELECCIONES, 'USD', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => c.monto), [383, 99]);
  assert.equal(r.total, 482);
});

test('sin extras la líder absorbe solo el residuo', () => {
  const sel = { pesca: { personas: 2, extras: [] }, traslado: { ...SELECCIONES.traslado, extras: [] } };
  const r = p.calcularPedido(PAQUETE, sel, 'MXN', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => c.monto), [6000, 1500]);
});

test('devuelve null si falta una tarifa, un precio en la moneda o la zona correcta', () => {
  assert.equal(p.calcularPedido(PAQUETE, SELECCIONES, 'MXN', {}), null);
  const sinUsd = { 'transportes-la-paz': [{ ...TARIFAS['transportes-la-paz'][0], precio_usd: null }] };
  assert.equal(p.calcularPedido(PAQUETE, SELECCIONES, 'USD', sinUsd), null);
  // La zona que llega aquí es la EFECTIVA (la del hotel para redondo_actividad); '' no encuentra tarifa de zona.
  const sinZona = { ...SELECCIONES, traslado: { ...SELECCIONES.traslado, traslado: { tipo: 'redondo_actividad', zona: '' } } };
  assert.equal(p.calcularPedido(PAQUETE, sinZona, 'MXN', TARIFAS), null);
});

test('un extra sin precio en USD hace que el pedido en USD no se pueda calcular', () => {
  const paquete = {
    ...PAQUETE,
    servicios_asociados: [servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00', null)])],
  };
  assert.equal(p.calcularPedido(paquete, { pesca: { personas: 2, extras: [{ id: 10 }] } }, 'USD', {}), null);
  assert.equal(p.calcularPedido(paquete, { pesca: { personas: 2, extras: [] } }, 'USD', {}).total, 450);
});

test('paquete de una sola empresa: un solo cargo = ancla + extras', () => {
  const mono = {
    empresa_lider_slug: 'sal-y-sol', precio_ancla: '9500.00', precio_ancla_usd: null,
    servicios_asociados: [servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00', '23.00')])],
  };
  const r = p.calcularPedido(mono, { pesca: { personas: 2, extras: [{ id: 10 }] } }, 'MXN', {});
  assert.deepEqual(r.cargos.map((c) => [c.empresaSlug, c.monto]), [['sal-y-sol', 9900]]);
  assert.equal(p.calcularPedido(mono, { pesca: { personas: 2, extras: [] } }, 'USD', {}), null);
});

test('USD solo se ofrece si TODOS los precios existen', () => {
  assert.equal(p.usdDisponible(PAQUETE, TARIFAS), true);
  assert.equal(p.usdDisponible({ ...PAQUETE, precio_ancla_usd: null }, TARIFAS), false);
});

test('anticipo: porcentaje del total; completo es el total', () => {
  assert.equal(p.montoInicial(9500, 'anticipo', 50), 4750);
  assert.equal(p.montoInicial(9500, 'completo', 50), 9500);
  assert.equal(p.montoInicial(1000, 'anticipo', 33), 330);
});
