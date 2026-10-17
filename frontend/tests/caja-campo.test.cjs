/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { CAJA_CAMPO, CAJA_CAMPO_ERROR, CAJA_CONTENEDOR, CAJA_CONTENEDOR_ERROR } = require(path.join(process.env.CAJA_CAMPO_TEST_OUT, 'components/ui/caja-campo.js'));

const tiene = (clases, nombre) => clases.split(' ').includes(nombre);

test('el campo mide 48 px en móvil y 44 en escritorio, con radio de campo y relleno blanco', () => {
  for (const clases of [CAJA_CAMPO, CAJA_CAMPO_ERROR, CAJA_CONTENEDOR, CAJA_CONTENEDOR_ERROR]) {
    for (const c of ['min-h-12', 'sm:min-h-11', 'rounded-campo', 'bg-superficie']) assert.ok(tiene(clases, c), c);
  }
});

test('el borde del campo es el de control (3:1), no el decorativo, y el foco lo pinta el anillo', () => {
  for (const clases of [CAJA_CAMPO, CAJA_CONTENEDOR]) {
    assert.ok(tiene(clases, 'border-borde-control'));
    assert.ok(tiene(clases, 'focus-within:border-ring'));
    assert.ok(tiene(clases, 'focus-within:ring-1'));
    assert.ok(tiene(clases, 'focus-within:ring-inset'));
    assert.ok(tiene(clases, 'focus-within:ring-ring'));
    assert.ok(!tiene(clases, 'border-border'));
  }
});

test('el error pinta el borde de 2 px en error, en reposo y en foco, sin cambiar el relleno', () => {
  for (const clases of [CAJA_CAMPO_ERROR, CAJA_CONTENEDOR_ERROR]) {
    assert.ok(tiene(clases, 'border-error'));
    assert.ok(tiene(clases, 'ring-1'));
    assert.ok(tiene(clases, 'ring-inset'));
    assert.ok(tiene(clases, 'ring-error'));
    assert.ok(tiene(clases, 'bg-superficie'));
    assert.ok(!tiene(clases, 'focus-within:border-ring'));
  }
});

test('el campo que se escribe trae 16 px de texto como mínimo, tinta, marcador apagado y deshabilitado en cafe-bruma', () => {
  for (const c of ['px-4', 'text-base', 'text-tinta', 'placeholder:text-apagado']) {
    assert.ok(tiene(CAJA_CAMPO, c), c);
    assert.ok(tiene(CAJA_CAMPO_ERROR, c), c);
  }
  assert.ok(tiene(CAJA_CAMPO, 'disabled:bg-cafe-bruma'));
  assert.ok(tiene(CAJA_CAMPO, 'disabled:text-apagado'));
});

test('el contenedor no pone relleno ni tamaño de texto: lo trae el control de adentro', () => {
  for (const clases of [CAJA_CONTENEDOR, CAJA_CONTENEDOR_ERROR]) {
    assert.ok(!tiene(clases, 'px-4'));
    assert.ok(!tiene(clases, 'text-base'));
  }
});

test('sin sombras arbitrarias, colores crudos ni paleta de Tailwind', () => {
  for (const clases of [CAJA_CAMPO, CAJA_CAMPO_ERROR, CAJA_CONTENEDOR, CAJA_CONTENEDOR_ERROR]) {
    assert.doesNotMatch(clases, /shadow-/);
    assert.doesNotMatch(clases, /#[0-9a-fA-F]{3,8}|rgba?[(]/);
    assert.doesNotMatch(clases, /-(red|green|blue|amber|gray)-[0-9]/);
  }
});
