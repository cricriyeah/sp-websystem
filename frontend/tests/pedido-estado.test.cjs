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


test('paquete variable inicia cada componente dentro de su cupo, sin afectar el fijo', () => {
  const s = e.estadoInicial({ ...PAQUETE, precio_depende_de_personas: true }, { moneda: 'MXN', puntoInicial: () => 7 });
  assert.deepEqual(Object.values(s.componentes).map((c) => c.personas), [3, 2]);
  assert.deepEqual(Object.values(inicial().componentes).map((c) => c.personas), [3, 2]);
});

test('la logística puede bajar sin cambiar las personas de actividad', () => {
  const previo = e.estadoInicial({ ...PAQUETE, precio_depende_de_personas: true }, { moneda: 'MXN', puntoInicial: () => 7 });
  const s = e.reducirPedido(previo, { tipo: 'personasLogistica', slug: 'traslado', slugPrincipal: 'pesca', valor: 1 });
  assert.deepEqual([s.componentes.pesca.personas, s.componentes.traslado.personas], [3, 1]);
  assert.deepEqual(s.componentes.traslado.traslado, previo.componentes.traslado.traslado);
});

test('al bajar actividad se ajusta hacia abajo la logística, sin subir la ya reducida', () => {
  const previo = e.estadoInicial({ ...PAQUETE, precio_depende_de_personas: true }, { moneda: 'MXN', puntoInicial: () => 7 });
  const reducido = e.reducirPedido(previo, { tipo: 'personasLogistica', slug: 'traslado', slugPrincipal: 'pesca', valor: 1 });
  const s = e.reducirPedido(reducido, { tipo: 'personasPaquete', slugPrincipal: 'pesca', valor: 2 });
  assert.deepEqual([s.componentes.pesca.personas, s.componentes.traslado.personas], [2, 1]);
  const menor = e.reducirPedido(s, { tipo: 'personasPaquete', slugPrincipal: 'pesca', valor: 1 });
  assert.deepEqual([menor.componentes.pesca.personas, menor.componentes.traslado.personas], [1, 1]);
  assert.deepEqual(s.componentes.pesca.extras, previo.componentes.pesca.extras);
});

test('la logística no puede superar a la actividad ni cambiar su número', () => {
  const previo = e.estadoInicial({ ...PAQUETE, precio_depende_de_personas: true }, { moneda: 'MXN', puntoInicial: () => 7 });
  const s = e.reducirPedido(previo, { tipo: 'personasPaquete', slugPrincipal: 'pesca', valor: 2 });
  const ajustado = e.reducirPedido(s, { tipo: 'personasLogistica', slug: 'traslado', slugPrincipal: 'pesca', valor: 4 });
  assert.deepEqual([ajustado.componentes.pesca.personas, ajustado.componentes.traslado.personas], [2, 2]);
});


test('hospedaje y traslado se limitan por la actividad aunque figuren antes o tengan menor cupo propio', () => {
  const paquete = { precio_depende_de_personas: true, servicios_asociados: [
    { orden: 1, personas_incluidas: 1, servicio: { slug: 'hotel', tipo_servicio: 'hospedaje', estrategia_cupo: 'por_noche', personalizaciones: [] } },
    { orden: 2, personas_incluidas: 4, servicio: { slug: 'pesca', tipo_servicio: 'pesca', estrategia_cupo: 'por_recurso_dia', personalizaciones: [] } },
    { orden: 3, personas_incluidas: 2, servicio: { slug: 'traslado', tipo_servicio: 'transporte', estrategia_cupo: 'bajo_demanda', personalizaciones: [] } },
  ] };
  let s = e.estadoInicial(paquete, { moneda: 'MXN', puntoInicial: () => 7 });
  assert.deepEqual([s.componentes.hotel.personas, s.componentes.pesca.personas, s.componentes.traslado.personas], [1, 4, 2]);
  s = e.reducirPedido(s, { tipo: 'personasLogistica', slug: 'hotel', slugPrincipal: 'pesca', valor: 2 });
  s = e.reducirPedido(s, { tipo: 'personasLogistica', slug: 'traslado', slugPrincipal: 'pesca', valor: 3 });
  s = e.reducirPedido(s, { tipo: 'personasPaquete', slugPrincipal: 'pesca', valor: 1 });
  assert.deepEqual([s.componentes.hotel.personas, s.componentes.pesca.personas, s.componentes.traslado.personas], [1, 1, 1]);
});

test('paquete con hospedaje de una empresa: el traslado arranca redondo con aeropuerto, sin aeropuerto elegido', () => {
  const s = e.estadoInicial({ ...PAQUETE, es_cruza_empresa: false, noches: 5 }, { moneda: 'MXN', puntoInicial: () => 7 });
  assert.equal(s.componentes.traslado.traslado.tipo, 'redondo_aeropuerto');
  assert.equal(s.componentes.traslado.traslado.aeropuerto, '');
});

test('paquete sin hospedaje conserva el tipo inicial de siempre', () => {
  assert.equal(inicial().componentes.traslado.traslado.tipo, 'redondo_actividad');
});

test('la hora inicial es la primera del rango de la actividad principal, o ninguna si el paquete no la pide', () => {
  const ventana = { pide_hora: true, hora_apertura: '08:00:00', hora_cierre: '10:00:00', paso_hora_minutos: 60 };
  const paquete = (pide) => ({
    pide_hora: pide,
    servicios_asociados: [{
      servicio_id: 1, orden: 1, personas_incluidas: 2,
      servicio: { slug: 'pesca', empresa_slug: 'a', tipo_servicio: 'pesca', estrategia_cupo: 'por_recurso_dia', personalizaciones: [], ...ventana },
    }],
  });
  assert.equal(e.estadoInicial(paquete(true), { moneda: 'MXN', puntoInicial: () => null }).hora, '08:00');
  assert.equal(e.estadoInicial(paquete(false), { moneda: 'MXN', puntoInicial: () => null }).hora, '');
});
