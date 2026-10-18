/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const v = require(path.join(process.env.VALIDAR_RESERVA_TEST_OUT, 'lib/validar-reserva.js'));

const P = (paso, campo) => ({ paso, campo, mensaje: `falta ${campo}` });

test('sin problemas devuelve null', () => {
  assert.equal(v.validarTodo([]), null);
  assert.equal(v.validarTodo([null, null]), null);
});

test('gana el paso más temprano aunque llegue después en la lista', () => {
  const r = v.validarTodo([P('datos', 'email'), P('viaje', 'fecha'), P('pago', 'deslinde')]);
  assert.equal(r.campo, 'fecha');
});

test('dentro de un mismo paso gana el primero de la lista', () => {
  const r = v.validarTodo([null, P('datos', 'phone'), P('datos', 'email')]);
  assert.equal(r.campo, 'phone');
});
