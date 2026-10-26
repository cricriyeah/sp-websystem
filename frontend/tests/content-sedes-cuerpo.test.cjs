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
  assert.equal(es.hero.video, '/videos/nuevo-hero.webm');
  assert.notEqual(es.hero.subtitulo, en.hero.subtitulo);
});

test('la-ventana existe con negocio null (temporada/incluye no viven aqui, viven en el dict global)', () => {
  const es = c.getSedeContenido('la-ventana', 'es');
  assert.ok(es);
  assert.equal(es.negocio, null);
  assert.equal(es.hero.video, '/videos/ventana-hero.webm');
  assert.ok(es.hero.imagen);
  assert.deepEqual(es.hero.facts, []);
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(c.getSedeContenido('cancun', 'es'), undefined);
  assert.equal(c.getSedeContenido('__proto__', 'es'), undefined);
});

test('Puerto Chale conserva la plantilla de La Ventana con identidad propia en ambos idiomas', () => {
  for (const lang of ['es', 'en']) {
    const chale = c.getSedeContenido('puerto-chale', lang);
    const ventana = c.getSedeContenido('la-ventana', lang);
    assert.equal(chale.nombre, 'Puerto Chale');
    assert.ok(chale.metaTitle.includes('Puerto Chale'));
    assert.ok(!chale.metaDescription.includes('La Ventana'));
    // Ninguna sede usa la ilustración rotulada «Destino Los Cabos» (2026-10-19): foto de relleno propia.
    for (const sede of [chale, ventana]) assert.ok(sede.hero.imagen.startsWith('/photos/'));
    assert.equal(chale.negocio, null);
    // Las tres protagonistas, confirmadas por el dueño (2026-10-16).
    assert.equal(chale.empresaProtagonistaSlug, 'piratas-adventures');
    assert.equal(ventana.empresaProtagonistaSlug, 'la-ventana-travel');
    assert.deepEqual(chale.destacadas, ventana.destacadas);
  }
  assert.equal(c.getSedeContenido('los-cabos', 'es'), undefined);
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
  assert.equal(cuerpo.empresaProtagonistaSlug, 'sal-y-sol');
  // Las demás empresas son slugs: sus datos salen de empresas.ts, no se duplican.
  assert.deepEqual(cuerpo.otrasEmpresas, []); // DLS Transporte desactivado por ahora
});

test('«Tu día» en La Paz y La Ventana con los mismos momentos en es y en; Puerto Chale sin él', () => {
  for (const slug of ['la-paz', 'la-ventana']) {
    const es = c.getSedeContenido(slug, 'es').dia;
    const en = c.getSedeContenido(slug, 'en').dia;
    assert.ok(es && en, slug);
    assert.equal(es.momentos.length, en.momentos.length, slug);
    assert.deepEqual(es.momentos.map((m) => m.foto), en.momentos.map((m) => m.foto), slug);
  }
  assert.equal(c.getSedeContenido('puerto-chale', 'es').dia, undefined);
});
