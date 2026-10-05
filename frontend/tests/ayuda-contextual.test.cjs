/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const a = require(path.join(process.env.AYUDA_CONTEXTUAL_TEST_OUT, 'lib/ayuda-contextual.js'));

const tropezar = (estado, tipo, veces) => {
  let actual = estado;
  for (let i = 0; i < veces; i += 1) actual = a.registrarTropiezo(actual, tipo);
  return actual;
};

test('al inicio no se ofrece ayuda', () => {
  assert.equal(a.ofreceAyudaFlotante(a.ayudaInicial), false);
});

test('se ofrece desde el tercer tropiezo de validación', () => {
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'validacion', 2)), false);
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'validacion', 3)), true);
});

test('se ofrece desde el tercer intento de pasar el tope de personas', () => {
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'tope-personas', 2)), false);
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'tope-personas', 3)), true);
});

test('los tropiezos de distinto tipo se suman', () => {
  const mezclado = tropezar(tropezar(a.ayudaInicial, 'validacion', 2), 'tope-personas', 1);
  assert.equal(a.ofreceAyudaFlotante(mezclado), true);
});

test('descartar apaga la ayuda y no vuelve a salir', () => {
  const descartada = a.descartarAyuda(tropezar(a.ayudaInicial, 'validacion', 3));
  assert.equal(a.ofreceAyudaFlotante(descartada), false);
  assert.equal(a.ofreceAyudaFlotante(a.registrarTropiezo(descartada, 'validacion')), false);
});

test('el motivo es el tipo de tropiezo que más veces ocurrió', () => {
  assert.equal(a.motivoDeAyuda(tropezar(a.ayudaInicial, 'tope-personas', 3)), 'tope-personas');
  assert.equal(a.motivoDeAyuda(tropezar(a.ayudaInicial, 'validacion', 3)), 'validacion');
  const mas_tope = tropezar(tropezar(a.ayudaInicial, 'validacion', 1), 'tope-personas', 2);
  assert.equal(a.motivoDeAyuda(mas_tope), 'tope-personas');
});

test('registrar un tropiezo no muta el estado anterior', () => {
  const antes = a.ayudaInicial;
  a.registrarTropiezo(antes, 'validacion');
  assert.equal(antes.validacion, 0);
});
