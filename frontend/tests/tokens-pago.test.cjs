/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { TOKENS_PAGO, RADIO_PAGO } = require(path.join(process.env.TOKENS_PAGO_TEST_OUT, 'lib/tokens-pago.js'));
const { resolverToken, declaraciones, leerGlobalsCss } = require('./ayudas/css-tokens.cjs');

const css = leerGlobalsCss();

test('los valores de Stripe Elements coinciden con los tokens de globals.css', () => {
  assert.equal(TOKENS_PAGO.colorPrimary, resolverToken(css, '--accent'));
  assert.equal(TOKENS_PAGO.colorText, resolverToken(css, '--foreground'));
  assert.equal(TOKENS_PAGO.colorTextSecondary, resolverToken(css, '--muted'));
  assert.equal(TOKENS_PAGO.colorBackground, resolverToken(css, '--superficie'));
  assert.equal(TOKENS_PAGO.colorDanger, resolverToken(css, '--error'));
});

test('la fuente de Stripe Elements es la pila del sistema de --font-sans, sin fuentes externas', () => {
  const pila = declaraciones(css).get('--font-sans');
  assert.ok(pila, '--font-sans no declarado');
  assert.equal(TOKENS_PAGO.fontFamily, pila);
  assert.doesNotMatch(TOKENS_PAGO.fontFamily, /Instrument|Bebas|Bella|Consola/);
});

test('el radio de Stripe Elements coincide con --radius-campo', () => {
  assert.equal(RADIO_PAGO, resolverToken(css, '--radius-campo'));
});

test('resolverToken sigue var() recursivo, convierte rem y falla si no termina en hex o px', () => {
  const demo = `
    :root { --a: var(--b); --b: #ABCDEF; --c: 0.75rem; --d: var(--e); --e: var(--d); --f: 1px solid red; }
    @media (min-width: 40rem) { :root { --a: #000000; } }
    @theme static { --g: var(--c); }
  `;
  assert.equal(resolverToken(demo, '--a'), '#abcdef');
  assert.equal(resolverToken(demo, '--g'), '12px');
  assert.throws(() => resolverToken(demo, '--d'), /Ciclo/);
  assert.throws(() => resolverToken(demo, '--f'), /no termina en hex ni px/);
  assert.throws(() => resolverToken(demo, '--nada'), /no declarado/);
});
