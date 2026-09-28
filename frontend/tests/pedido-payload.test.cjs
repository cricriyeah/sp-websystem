/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PEDIDO_PAYLOAD_TEST_OUT, 'lib/pedido-payload.js'));

const svc = (id, slug, empresa, tipo, estrategia, extra = {}) => ({
  id, servicio_id: id, orden: id, dia_estancia: 1, noches: null, personas_incluidas: 3,
  servicio: { id, slug, empresa_slug: empresa, tipo_servicio: tipo, estrategia_cupo: estrategia, personalizaciones: [] },
  ...extra,
});

const CRUZA = {
  slug: 'pesca-traslado', empresa_lider_slug: 'sal-y-sol', noches: null,
  servicios_asociados: [
    svc(1, 'pesca', 'sal-y-sol', 'pesca', 'por_recurso_dia'),
    svc(2, 'traslado', 'transportes-la-paz', 'transporte', 'bajo_demanda'),
  ],
};

const traslado = (over = {}) => ({
  tipo: 'redondo_actividad', modo: 'catalogo', puntoEncuentroId: 7, direccion: '', zonaLibre: '', fechaRegreso: null, ...over,
});

const COMPONENTES = {
  pesca: { personas: 2, extras: [{ id: 10 }] },
  traslado: { personas: 3, extras: [{ id: 20 }], traslado: traslado() },
};

const BASE = {
  checkoutId: 'chk-1', inicio: '2026-10-15', hora: '07:00', moneda: 'MXN',
  contacto: { fullName: ' Ana Ruiz ', phone: ' 6121234567 ', email: 'ana@example.com' },
  ref: 'amigo', zonaDePunto: () => 'centro',
};

test('zona efectiva: solo cuenta en redondo_actividad', () => {
  const zona = () => 'periferia';
  assert.equal(p.zonaEfectivaDeTraslado(traslado(), zona), 'periferia');
  assert.equal(p.zonaEfectivaDeTraslado(traslado({ modo: 'personalizada', zonaLibre: 'centro' }), zona), 'centro');
  assert.equal(p.zonaEfectivaDeTraslado(traslado({ tipo: 'redondo_aeropuerto' }), zona), '');
  assert.equal(p.zonaEfectivaDeTraslado(traslado({ tipo: 'recepcion_aeropuerto' }), zona), '');
});

test('la orden manda un inicio, personas y extras por componente, sin fechas por servicio', () => {
  const r = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: COMPONENTES });
  assert.equal(r.fecha, '2026-10-15');
  assert.equal(r.deslinde_nombre, 'Ana Ruiz');
  assert.deepEqual(r.componentes.map((c) => [c.servicio, c.numero_personas]), [['pesca', 2], ['traslado', 3]]);
  assert.deepEqual(r.componentes[0].personalizaciones, [{ id: 10 }]);
  const t = r.componentes[1];
  assert.equal(t.tipo_traslado, 'redondo_actividad');
  assert.equal(t.punto_encuentro, 7);
  assert.equal(t.zona, 'centro');
  assert.equal('fecha' in t, false);
});

test('aeropuerto con hotel del catálogo no manda la zona del hotel (sus tarifas no llevan zona)', () => {
  const comp = { ...COMPONENTES, traslado: { ...COMPONENTES.traslado, traslado: traslado({ tipo: 'redondo_aeropuerto' }) } };
  const r = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: comp });
  assert.equal(r.componentes[1].zona, '');
  assert.equal(r.componentes[1].punto_encuentro, 7);
});

test('dirección libre manda dirección y zona elegida solo en redondo_actividad', () => {
  const comp = { ...COMPONENTES, traslado: { ...COMPONENTES.traslado, traslado: traslado({ modo: 'personalizada', direccion: ' Calle 1 ', zonaLibre: 'periferia', puntoEncuentroId: null }) } };
  const t = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: comp }).componentes[1];
  assert.equal(t.direccion_personalizada, 'Calle 1');
  assert.equal(t.zona, 'periferia');
  assert.equal('punto_encuentro' in t, false);
});

test('fecha_regreso del aeropuerto solo viaja si el paquete no tiene hospedaje', () => {
  const comp = { ...COMPONENTES, traslado: { ...COMPONENTES.traslado, traslado: traslado({ tipo: 'redondo_aeropuerto', fechaRegreso: '2026-10-18' }) } };
  const sin = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: comp });
  assert.equal(sin.componentes[1].fecha_regreso, '2026-10-18');
  const con = p.armarPayloadOrden({ ...BASE, paquete: { ...CRUZA, noches: 3 }, componentes: comp });
  assert.equal(con.componentes[1].fecha_regreso, undefined);
});

const MONO = {
  slug: 'finde', empresa_lider_slug: 'sal-y-sol', noches: 3,
  servicios_asociados: [
    svc(5, 'hotel', 'sal-y-sol', 'hospedaje', 'por_noche', { noches: 3 }),
    svc(6, 'pesca', 'sal-y-sol', 'pesca', 'por_recurso_dia', { dia_estancia: 2 }),
  ],
};

test('personas principales: las del primer componente por_recurso_dia', () => {
  const comps = { hotel: { personas: 1, extras: [] }, pesca: { personas: 3, extras: [] } };
  assert.equal(p.personasPrincipales(MONO, comps), 3);
});

test('la reserva manda personas por servicio (por id), inicio y todos los extras, sin fecha_salida', () => {
  const comps = { hotel: { personas: 1, extras: [{ id: 1 }] }, pesca: { personas: 3, extras: [{ id: 2 }] } };
  const r = p.armarPayloadReserva({ ...BASE, paquete: MONO, componentes: comps });
  assert.equal(r.fecha, '2026-10-15');
  assert.equal(r.paquete, 'finde');
  assert.equal(r.numero_personas, 3);
  assert.deepEqual(r.personas_por_servicio, { 5: 1, 6: 3 });
  assert.deepEqual(r.personalizaciones.map((x) => x.id), [1, 2]);
  assert.equal(r.fecha_salida, undefined);
});
