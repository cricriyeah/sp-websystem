/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const p = require(path.join(process.env.PEDIDO_PAQUETE_TEST_OUT, 'lib/pedido-paquete.js'));
const { calcularBasePaquete } = require(path.join(process.env.PEDIDO_PAQUETE_TEST_OUT, 'lib/precio-paquete.js'));
const casos = JSON.parse(fs.readFileSync(path.join(__dirname, '../../shared/precios_paridad.json'), 'utf8'));
const check = (id, precio) => ({ id, tipo_interaccion: 'check', cobrar_por_persona: false,
  cantidad_editable: false, precio });
const servicio = (slug, empresa, tipo, extras, incluidas = 3) => ({
  id: slug === 'pesca' ? 1 : 2, orden: slug === 'pesca' ? 1 : 2, personas_incluidas: incluidas,
  servicio: { slug, empresa_slug: empresa, tipo_servicio: tipo,
    estrategia_cupo: tipo === 'pesca' ? 'por_recurso_dia' : 'bajo_demanda', personalizaciones: extras },
});
const PAQUETE = {
  empresa_lider_slug: 'sal-y-sol', precio_ancla: '7500.00', tipo_cambio_usd: '18.0000',
  estrategia_precio: 'por_grupo', personas_precio_base: 3, precio_persona_extra: '0.00',
  precio_depende_de_personas: false,
  servicios_asociados: [
    servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00')]),
    servicio('traslado', 'transportes-la-paz', 'transporte', [check(20, '150.00')]),
  ],
};
const TARIFAS = { 'transportes-la-paz': [{ tipo_traslado: 'redondo_actividad', zona: 'centro',
  personas_min: 1, personas_max: null, precio: '1500.00' }] };
const SELECCIONES = {
  pesca: { personas: 2, extras: [{ id: 10 }] },
  traslado: { personas: 2, extras: [{ id: 20 }], traslado: { tipo: 'redondo_actividad', zona: 'centro' } },
};

test('reparto MXN del paquete fijo y extras', () => {
  const r = p.calcularPedido(PAQUETE, SELECCIONES, 'MXN', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => c.monto), [6400, 1650]);
  assert.equal(r.total, 8050);
});
test('USD convierte base, tarifa y cada extra antes de repartir', () => {
  const r = p.calcularPedido(PAQUETE, SELECCIONES, 'USD', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => c.monto), [356, 93]);
  assert.equal(r.total, 449);
});
test('sin extras la líder absorbe el residuo', () => {
  const sel = { pesca: { personas: 2, extras: [] }, traslado: { ...SELECCIONES.traslado, extras: [] } };
  assert.deepEqual(p.calcularPedido(PAQUETE, sel, 'MXN', TARIFAS).cargos.map((c) => c.monto), [6000, 1500]);
});
test('falta de tarifa o zona efectiva devuelve null', () => {
  assert.equal(p.calcularPedido(PAQUETE, SELECCIONES, 'MXN', {}), null);
  const sinZona = { ...SELECCIONES, traslado: { ...SELECCIONES.traslado,
    traslado: { tipo: 'redondo_actividad', zona: '' } } };
  assert.equal(p.calcularPedido(PAQUETE, sinZona, 'MXN', TARIFAS), null);
});
test('USD se ofrece con tipo de cambio positivo', () => {
  assert.equal(p.usdDisponible(PAQUETE), true);
  assert.equal(p.usdDisponible({ ...PAQUETE, tipo_cambio_usd: '0' }), false);
});
test('por persona cobra base por el grupo mayor y conserva reparto', () => {
  const paquete = { ...PAQUETE, estrategia_precio: 'por_persona', precio_ancla: '45000.00',
    precio_depende_de_personas: true };
  const r = p.calcularPedido(paquete, SELECCIONES, 'MXN', TARIFAS);
  assert.equal(r.total, 90550);
  assert.deepEqual(r.cargos.map((c) => c.monto), [88900, 1650]);
  const logisticaMenor = { pesca: { personas: 3, extras: [] },
    traslado: { ...SELECCIONES.traslado, personas: 1, extras: [] } };
  assert.equal(p.calcularPedido(paquete, logisticaMenor, 'MXN', TARIFAS).total, 135000);
});
test('grupo con extra cobra solo quienes superan la base', () => {
  const paquete = { ...PAQUETE, personas_precio_base: 2, precio_persona_extra: '500.00',
    precio_depende_de_personas: true };
  const sel = { pesca: { personas: 3, extras: [{ id: 10 }] },
    traslado: { ...SELECCIONES.traslado, personas: 2 } };
  assert.equal(p.calcularPedido(paquete, sel, 'MXN', TARIFAS).total, 8550);
  assert.equal(p.calcularPedido(paquete, sel, 'USD', TARIFAS).total, 477);
});
test('selección logística no puede superar a la actividad cuando el precio depende del grupo', () => {
  const paquete = { ...PAQUETE, personas_precio_base: 2, precio_persona_extra: '500.00',
    precio_depende_de_personas: true };
  const sel = { pesca: { personas: 2, extras: [] }, traslado: { ...SELECCIONES.traslado, personas: 3 } };
  assert.equal(p.calcularPedido(paquete, sel, 'MXN', TARIFAS), null);
});
test('fixture compartido de cálculo de paquetes', () => {
  for (const caso of casos.paquetes) {
    const paquete = { precio_ancla: caso.base, tipo_cambio_usd: caso.tipo_cambio,
      estrategia_precio: caso.estrategia, personas_precio_base: caso.personas_base,
      precio_persona_extra: caso.extra };
    assert.equal(calcularBasePaquete(paquete, caso.moneda, caso.personas), Number(caso.esperado));
  }
});
test('anticipo y tope principal siguen usando la misma selección', () => {
  assert.equal(p.montoInicial(9500, 'anticipo', 30), 2850);
  assert.equal(p.maxPersonasPaquete(PAQUETE), 3);
  assert.equal(p.servicioPrincipalPaquete(PAQUETE).servicio.slug, 'pesca');
});
test('traslado fijo de aeropuerto solo en paquete de una empresa con hospedaje', () => {
  assert.equal(p.trasladoFijoAeropuerto({ es_cruza_empresa: false, noches: 5 }), true);
  assert.equal(p.trasladoFijoAeropuerto({ es_cruza_empresa: false, noches: null }), false);
  assert.equal(p.trasladoFijoAeropuerto({ es_cruza_empresa: true, noches: 5 }), false);
});
