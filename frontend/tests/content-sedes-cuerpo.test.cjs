/* eslint-disable @typescript-eslint/no-require-imports */
//
// `sedes-cuerpo.ts` hace `import 'server-only'` a proposito (ver Step 1 de
// mas abajo): ese paquete no existe fuera del bundler de Next (no esta en
// package.json — Next lo resuelve con un alias interno), asi que un
// `require` directo del compilado revienta con "Cannot find module
// 'server-only'" en un `node --test` normal. Se stubea localmente, solo
// para este proceso de test: node busca `node_modules/server-only` subiendo
// directorios desde el archivo que hace el require, asi que un stub en la
// raiz del outDir compilado (un nivel arriba de `content/`) resuelve antes
// de tocar el paquete real.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

const outDir = process.env.CONTENT_SEDES_CUERPO_TEST_OUT;
const stubDir = path.join(outDir, 'node_modules', 'server-only');
fs.mkdirSync(stubDir, { recursive: true });
fs.writeFileSync(path.join(stubDir, 'package.json'), JSON.stringify({ name: 'server-only', main: 'index.js' }));
fs.writeFileSync(path.join(stubDir, 'index.js'), 'module.exports = {};');

const c = require(path.join(outDir, 'content/sedes-cuerpo.js'));

test('la-paz existe en los dos idiomas con hero y negocio no nulos', () => {
  const es = c.getSedeContenido('la-paz', 'es');
  const en = c.getSedeContenido('la-paz', 'en');
  assert.ok(es);
  assert.ok(en);
  assert.equal(es.slug, 'la-paz');
  assert.equal(es.nombre, 'La Paz');
  assert.equal(es.negocio.ciudad, 'La Paz');
  assert.equal(es.hero.video, '/videos/videohero.webm');
  assert.notEqual(es.hero.titulo.start, en.hero.titulo.start);
});

test('los-cabos existe con negocio null (temporada/incluye no viven aqui, viven en el dict global)', () => {
  const es = c.getSedeContenido('los-cabos', 'es');
  assert.ok(es);
  assert.equal(es.negocio, null);
  assert.equal(es.hero.video, null);
  assert.ok(es.hero.imagen);
  assert.deepEqual(es.hero.facts, []);
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(c.getSedeContenido('cancun', 'es'), undefined);
  assert.equal(c.getSedeContenido('__proto__', 'es'), undefined);
});

test('cada destacada inlineable de la-paz apunta al flujo de pesca legacy', () => {
  const es = c.getSedeContenido('la-paz', 'es');
  const inlineables = es.destacadas.filter((d) => d.inlineable);
  assert.equal(inlineables.length, 1);
  assert.equal(inlineables[0].tipo, 'servicio');
  assert.equal(inlineables[0].slug, 'pesca-deportiva');
});

test('getSedeCuerpo no trae slug/nombre/logo del indice (solo el cuerpo crudo)', () => {
  const cuerpo = c.getSedeCuerpo('la-paz', 'es');
  assert.ok(cuerpo);
  assert.equal(cuerpo.nombre, undefined);
  assert.equal(cuerpo.logo, undefined);
  assert.equal(cuerpo.empresaFundadoraSlug, 'sal-y-sol');
});
