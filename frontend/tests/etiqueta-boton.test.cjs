/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const e = require(path.join(process.env.ETIQUETA_BOTON_TEST_OUT, 'lib/etiqueta-boton.js'));

const textos = {
  continuarAPago: 'Continuar a pago',
  pagarUno: 'Pagar {amount}',
  pagarA: 'Pagar {amount} a {empresa}',
  pagoNDeTotal: 'Pago {n} de {total}',
};

test('sin monto confirmado nunca hay cifra, en ningún paso', () => {
  for (const paso of ['viaje', 'datos', 'pago']) {
    const etiqueta = e.etiquetaDeBoton({ paso, montoConfirmado: null, textos });
    assert.doesNotMatch(etiqueta, /\d/, paso);
  }
  assert.equal(e.etiquetaDeBoton({ paso: 'pago', montoConfirmado: null, textos }), 'Continuar a pago');
});

test('un monto en blanco no cuenta como confirmado', () => {
  assert.equal(e.etiquetaDeBoton({ paso: 'pago', montoConfirmado: '', textos }), 'Continuar a pago');
});

test('con un solo cobro y monto confirmado, el botón lleva la cifra', () => {
  assert.equal(e.etiquetaDeBoton({ paso: 'pago', montoConfirmado: '$4,100 MXN', textos }), 'Pagar $4,100 MXN');
});

test('con monto y empresa, el texto incluye empresa y cifra', () => {
  const etiqueta = e.etiquetaDeBoton({
    paso: 'pago', montoConfirmado: '$4,100 MXN', empresa: 'Sal y Sol', cargos: { n: 1, total: 2 }, textos,
  });
  assert.match(etiqueta, /\$4,100 MXN/);
  assert.match(etiqueta, /Sal y Sol/);
});

test('los pagos de varias empresas se numeran «Pago 1 de 2» y «Pago 2 de 2»', () => {
  assert.equal(e.rotuloDePago(1, 2, textos), 'Pago 1 de 2');
  assert.equal(e.rotuloDePago(2, 2, textos), 'Pago 2 de 2');
});

test('en Viaje y Datos el botón nunca lleva monto aunque se conozca', () => {
  for (const paso of ['viaje', 'datos']) {
    const etiqueta = e.etiquetaDeBoton({ paso, montoConfirmado: '$4,100 MXN', textos });
    assert.doesNotMatch(etiqueta, /\d/, paso);
  }
});
