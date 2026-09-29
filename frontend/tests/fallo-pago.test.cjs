/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const f = require(path.join(process.env.FALLO_PAGO_TEST_OUT, 'lib/fallo-pago.js'));

test('traduce los códigos comunes del banco a una clave propia', () => {
  assert.equal(f.claveMotivoRechazo('insufficient_funds'), 'insufficient_funds');
  assert.equal(f.claveMotivoRechazo('expired_card'), 'expired_card');
  assert.equal(f.claveMotivoRechazo('incorrect_cvc'), 'incorrect_cvc');
  assert.equal(f.claveMotivoRechazo('invalid_cvc'), 'incorrect_cvc');
  assert.equal(f.claveMotivoRechazo('authentication_required'), 'authentication_required');
  assert.equal(f.claveMotivoRechazo('card_declined'), 'card_declined');
  assert.equal(f.claveMotivoRechazo('generic_decline'), 'card_declined');
});

test('un código desconocido o ausente cae en el texto genérico', () => {
  assert.equal(f.claveMotivoRechazo('algo_raro'), 'generic');
  assert.equal(f.claveMotivoRechazo(undefined), 'generic');
  assert.equal(f.claveMotivoRechazo(''), 'generic');
});

test('extrae la empresa de un fallo de captura del servidor', () => {
  assert.equal(f.empresaDeFalloCaptura('no se pudo capturar transportes-la-paz'), 'transportes-la-paz');
  assert.equal(f.empresaDeFalloCaptura('la retención del pago no se completó'), null);
  assert.equal(f.empresaDeFalloCaptura(''), null);
});

test('ofrece ayuda de la vendedora desde el tercer fallo', () => {
  assert.equal(f.ofreceAyuda(2), false);
  assert.equal(f.ofreceAyuda(3), true);
  assert.equal(f.ofreceAyuda(5), true);
});

test('los pagos retenidos antes del rechazo son los anteriores al índice', () => {
  const pagos = [{ empresaSlug: 'a', monto: '6400' }, { empresaSlug: 'b', monto: '1650' }];
  assert.deepEqual(f.pagosRetenidosAntes(pagos, 1), [pagos[0]]);
  assert.deepEqual(f.pagosRetenidosAntes(pagos, 0), []);
  assert.deepEqual(f.pagosRetenidosAntes(pagos, null), []);
});
