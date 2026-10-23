/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.REGLA_PERSONAS_TEST_OUT, 'lib/regla-personas.js'));

const t = {
  grupoCubre: 'cubre {n} · desde la {m}.ª +{precio}',
  grupoExtra: 'extra {k} × {precio} = +{monto}',
  grupoFijo: 'mismo de 1 a {max}',
  persona: '{precio} × {n} = {monto}',
  rango: '{min}–{max}: {precio}',
  rangoSiguiente: 'desde {k}: {precio}',
  incluido: 'incluido',
};
const f = (n) => `$${n}`;

test('grupo: antes de cruzar dice qué cubre y cuánto cuesta la siguiente persona', () => {
  const regla = { tipo: 'grupo', incluidas: 2, extra: 1350, maximo: 5 };
  assert.equal(m.textoRegla(regla, 1, f, t), 'cubre 2 · desde la 3.ª +$1350');
  assert.equal(m.textoRegla(regla, 2, f, t), 'cubre 2 · desde la 3.ª +$1350');
});

test('grupo: al cruzar dice cuántas personas extra y cuánto suman', () => {
  const regla = { tipo: 'grupo', incluidas: 2, extra: 1350, maximo: 5 };
  assert.equal(m.textoRegla(regla, 3, f, t), 'extra 1 × $1350 = +$1350');
  assert.equal(m.textoRegla(regla, 5, f, t), 'extra 3 × $1350 = +$4050');
});

test('grupo: sin cargo extra (o si cubre el máximo) es el mismo precio', () => {
  assert.equal(m.textoRegla({ tipo: 'grupo', incluidas: 3, extra: 0, maximo: 3 }, 2, f, t), 'mismo de 1 a 3');
  assert.equal(m.textoRegla({ tipo: 'grupo', incluidas: 5, extra: 100, maximo: 5 }, 4, f, t), 'mismo de 1 a 5');
});

test('persona: el precio por persona y lo que suma el grupo', () => {
  assert.equal(m.textoRegla({ tipo: 'persona', precio: 5000 }, 3, f, t), '$5000 × 3 = $15000');
});

test('rangos: el rango actual y, si cambia el precio, desde cuántos', () => {
  const regla = { tipo: 'rangos', rangos: [{ min: 5, max: 8, precio: 3500 }, { min: 1, max: 4, precio: 2700 }] };
  assert.equal(m.textoRegla(regla, 2, f, t), '1–4: $2700 · desde 5: $3500');
  assert.equal(m.textoRegla(regla, 6, f, t), '5–8: $3500');
  assert.equal(m.textoRegla(regla, 12, f, t), null);
});

test('incluido: dentro del paquete no cuesta', () => {
  assert.equal(m.textoRegla({ tipo: 'incluido' }, 4, f, t), 'incluido');
});
