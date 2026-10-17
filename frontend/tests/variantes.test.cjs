/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { botonClases } = require(path.join(process.env.VARIANTES_TEST_OUT, 'components/ui/variantes.js'));

test('R5: solo la variante principal usa el color de acción', () => {
  assert.match(botonClases({ variante: 'principal' }), /bg-action/);
  for (const v of ['secundario', 'texto', 'acento', 'peligro']) {
    assert.doesNotMatch(botonClases({ variante: v }), /bg-action/);
  }
});

test('área táctil mínima de 40 px en las acciones de texto', () => {
  assert.match(botonClases({ variante: 'texto' }), /min-h-10/);
});

test('la forma sale de tokens, no de utilidades crudas', () => {
  assert.match(botonClases({ variante: 'principal' }), /rounded-control/);
  assert.doesNotMatch(botonClases({ variante: 'principal' }), /rounded-full/);
});

test('sin colores crudos', () => {
  for (const v of ['principal', 'secundario', 'texto', 'acento', 'peligro']) {
    assert.doesNotMatch(botonClases({ variante: v }), /-(red|green|blue|amber)-\d/);
  }
});
