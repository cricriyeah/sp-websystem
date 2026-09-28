/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const e = require(path.join(process.env.PEDIDO_ESTADO_TEST_OUT, 'lib/pedido-estado.js'));

const PAQUETE = {
  servicios_asociados: [
    { servicio_id: 1, personas_incluidas: 3, servicio: { slug: 'pesca', empresa_slug: 'sal-y-sol', tipo_servicio: 'pesca', personalizaciones: [{ id: 10, tipo_interaccion: 'check', preseleccionado: true }] } },
    { servicio_id: 2, personas_incluidas: 2, servicio: { slug: 'traslado', empresa_slug: 'transp', tipo_servicio: 'transporte', personalizaciones: [] } },
  ],
};

const inicial = () => e.estadoInicial(PAQUETE, { moneda: 'MXN', puntoInicial: () => 7 });

test('arranca con las personas incluidas, los extras preseleccionados y sin fecha', () => {
  const s = inicial();
  assert.equal(s.inicio, null);
  assert.equal(s.componentes.pesca.personas, 3);
  assert.deepEqual(s.componentes.pesca.extras, [{ id: 10, cantidad: 1 }]);
  assert.equal(s.componentes.traslado.traslado.puntoEncuentroId, 7);
  assert.equal(s.componentes.pesca.traslado, undefined);
});

test('cambiar personas de un componente no toca a los demás', () => {
  const s = e.reducirPedido(inicial(), { tipo: 'personas', slug: 'pesca', valor: 1 });
  assert.equal(s.componentes.pesca.personas, 1);
  assert.equal(s.componentes.traslado.personas, 2);
});

test('cambios parciales del traslado se mezclan', () => {
  const s = e.reducirPedido(inicial(), { tipo: 'traslado', slug: 'traslado', cambios: { tipo: 'redondo_aeropuerto', fechaRegreso: '2026-10-18' } });
  assert.equal(s.componentes.traslado.traslado.tipo, 'redondo_aeropuerto');
  assert.equal(s.componentes.traslado.traslado.puntoEncuentroId, 7);
});

test('contacto, inicio, moneda y forma de pago', () => {
  let s = e.reducirPedido(inicial(), { tipo: 'contacto', cambios: { fullName: 'Ana' } });
  s = e.reducirPedido(s, { tipo: 'inicio', valor: '2026-10-15' });
  s = e.reducirPedido(s, { tipo: 'moneda', valor: 'USD' });
  s = e.reducirPedido(s, { tipo: 'formaPago', valor: 'anticipo' });
  assert.deepEqual([s.contacto.fullName, s.contacto.phone, s.inicio, s.moneda, s.formaPago], ['Ana', '', '2026-10-15', 'USD', 'anticipo']);
});
