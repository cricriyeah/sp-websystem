/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { DURACION, CURVA_ESTANDAR, CURVA_SALIDA, transicion } = require(path.join(process.env.MOVIMIENTO_TEST_OUT, 'lib/movimiento.js'));
const { declaraciones, leerGlobalsCss } = require('./ayudas/css-tokens.cjs');

const tokens = declaraciones(leerGlobalsCss());
const ms = (nombre) => {
  const m = /^(\d+)ms$/.exec(tokens.get(nombre));
  assert.ok(m, `${nombre} no está en ms`);
  return Number(m[1]);
};
const curva = (nombre) => {
  const m = /^cubic-bezier\(([^)]+)\)$/.exec(tokens.get(nombre));
  assert.ok(m, `${nombre} no es una curva`);
  return m[1].split(',').map(Number);
};

test('las duraciones de Framer Motion coinciden con los tokens de globals.css', () => {
  assert.equal(DURACION.corta * 1000, ms('--duracion-corta'));
  assert.equal(DURACION.media * 1000, ms('--duracion-media'));
  assert.equal(DURACION.larga * 1000, ms('--duracion-larga'));
});

test('las curvas de Framer Motion coinciden con los tokens de globals.css', () => {
  assert.deepEqual([...CURVA_ESTANDAR], curva('--curva-estandar'));
  assert.deepEqual([...CURVA_SALIDA], curva('--curva-salida'));
});

test('con reducir movimiento solo hay un fundido de duracion-corta, sin curva', () => {
  assert.deepEqual(transicion(true), { duration: DURACION.corta });
  assert.deepEqual(transicion(true, DURACION.larga), { duration: DURACION.corta });
});

test('sin reducir movimiento usa la duración pedida (media por defecto) y la curva estándar', () => {
  assert.deepEqual(transicion(false), { duration: DURACION.media, ease: CURVA_ESTANDAR });
  assert.deepEqual(transicion(null, DURACION.corta), { duration: DURACION.corta, ease: CURVA_ESTANDAR });
});
