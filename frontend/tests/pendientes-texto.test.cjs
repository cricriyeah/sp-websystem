/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { textoDeSituacion } = require(path.join(process.env.PENDIENTES_TEXTO_TEST_OUT, 'lib/pendientes-texto.js'));
const es = require('../src/app/[lang]/dictionaries/es.json').continuar;
const en = require('../src/app/[lang]/dictionaries/en.json').continuar;

const reserva = (situacion, extra = {}) => ({
  situacion, producto: 'Pesca', monto: '250.00', moneda: 'MXN',
  forma_pago: 'completo', folio: 4, vence_en: null, ...extra,
});
const orden = (situacion, extra = {}) => ({
  situacion, producto: 'Pesca + Traslado', moneda: 'MXN', forma_pago: 'completo',
  folio: 8, vence_en: '2026-10-15T15:40:00-07:00', actualizado_en: '2026-10-14T15:40:00-07:00',
  montos: [
    { empresa: 'Sal y Sol', monto: '6400.00', monto_reembolsado: null, estado: 'requires_capture' },
    { empresa: 'Transportes La Paz', monto: '1650.00', monto_reembolsado: null, estado: null },
  ], ...extra,
});

test('sin_pago usa el texto exacto y permite descartar', () => {
  const t = textoDeSituacion(es, reserva('sin_pago', { monto: null }));
  assert.equal(t.linea1, 'Pesca · Tus datos están guardados · Aún no has pagado');
  assert.equal(t.registro, 'en_curso');
  assert.equal(t.principal, es.botonContinuar);
  assert.equal(t.secundaria, es.botonDescartar);
});

test('retenido_parcial identifica empresa, importe faltante y vencimiento reales', () => {
  const t = textoDeSituacion(es, orden('retenido_parcial'));
  assert.equal(t.registro, 'con_dinero');
  assert.match(t.linea1, /Sal y Sol/);
  assert.match(t.linea1, /Transportes La Paz/);
  assert.match(t.linea1, /1,650/);
  assert.match(t.linea1, /3:40/);
  assert.match(t.linea1, /15 de octubre/);
  assert.equal(t.requiereConfirmacion, true);
});

for (const situacion of ['retenido_total', 'confirmando_cobro', 'pago_en_proceso',
  'cancelada_liberada',
  'cancelada_devolucion_por_confirmar', 'expirada', 'no_existe']) {
  test(`${situacion}: produce texto y acciones definidos`, () => {
    const t = textoDeSituacion(es, orden(situacion));
    assert.ok(t.linea1.length > 10);
    assert.ok(t.principal.length > 0);
    assert.ok(['en_curso', 'con_dinero', 'informativo'].includes(t.registro));
    assert.equal(typeof t.requiereConfirmacion, 'boolean');
  });
}

test('confirmada informa y solo permite cerrar el aviso', () => {
  const t = textoDeSituacion(es, orden('confirmada'));
  assert.match(t.linea1, /confirmada/);
  assert.equal(t.principal, null);
  assert.equal(t.secundaria, es.botonCerrar);
});

test('devolucion solicitada lleva folio y ofrece WhatsApp', () => {
  const t = textoDeSituacion(es, orden('cancelada_devolucion_solicitada'));
  assert.match(t.linea1, /Folio #8/);
  assert.equal(t.principal, es.botonWhatsApp);
  assert.equal(t.secundaria, es.botonEntendido);
});

test('anticipo confirmado se distingue de pago completo', () => {
  const t = textoDeSituacion(es, reserva('confirmada', { forma_pago: 'anticipo' }));
  assert.match(t.linea1, /anticipo/);
  assert.doesNotMatch(t.linea1, /Se cobró \$/);
  assert.equal(t.principal, null);
});

test('no inventa un monto de pago cuando el servidor no lo entrega', () => {
  const t = textoDeSituacion(en, reserva('pago_en_proceso', { monto: null }));
  assert.doesNotMatch(t.linea1, /\$0/);
  assert.equal(t.principal, en.botonVerEstado);
});
