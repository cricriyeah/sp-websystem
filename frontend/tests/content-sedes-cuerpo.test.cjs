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
  assert.equal(es.hero.video, '/videos/videonuevonuevolapaz.mp4');
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

test('«Conócenos» de La Paz: historia de todos (sin cifras sueltas), prensa, tripulación y cierre en los dos idiomas', () => {
  const es = c.getSedeContenido('la-paz', 'es').conocenos;
  const en = c.getSedeContenido('la-paz', 'en').conocenos;
  for (const k of [es, en]) {
    assert.ok(k.titulo && k.apertura);
    assert.equal(k.historia.length, 3, 'un relato en tres párrafos');
    assert.ok(k.historia.join(' ').split(/\s+/).length >= 150, 'texto largo, de trayectoria e historia');
    assert.ok(!('hechos' in k), 'sin cifras sueltas: se leían como estadísticas');
    assert.match(k.historia.join(' '), /(gremio|guild)/, 'el protagonista es el grupo, no una persona');
    assert.ok(/Peninsular Digital, 2010/.test(k.prensa.fuente) && /(motor|engine)/.test(k.prensa.texto));
    assert.equal(k.tripulacion.fotos.length, 3);
    assert.equal(k.tripulacion.capitanes[0].nombre, 'Rogelio');
    assert.ok(k.foto.src.startsWith('/photos/') && k.foto.alt);
    assert.ok(!k.foto.src.includes('sobre-nosotros'), 'no el retrato del jefe solo');
    assert.deepEqual(Object.keys(k.cierre), ['boton'], 'el cierre es el logo largo y el botón, sin título ni frase');
    const todo = JSON.stringify(k);
    assert.ok(!todo.includes('1950'), 'sin año de fundación');
    assert.ok(!/[—–]/.test(todo), 'sin guiones largos');
    assert.ok(!/n[uú]mero uno|number one|#1/i.test(todo), 'ningún superlativo sin prueba');
  }
  assert.equal(es.foto.src, en.foto.src);
  assert.deepEqual(es.tripulacion.capitanes.map((x) => x.nombre), en.tripulacion.capitanes.map((x) => x.nombre));
});

test('«Conócenos» de La Paz: los ocho capitanes confirmados por el dueño (2026-10-30) se publican, en los dos idiomas', () => {
  for (const lang of ['es', 'en']) {
    const capitanes = c.getSedeContenido('la-paz', lang).conocenos.tripulacion.capitanes;
    assert.deepEqual(capitanes.map((x) => x.nombre), ['Rogelio', 'Omar', 'Alfredo', 'Joel', 'Icho', 'Julio', 'Raúl', 'Dagoberto']);
    assert.ok(capitanes.every((x) => !x.pendiente));
  }
});

test('las pangas de La Paz: la flota completa, sus siete nombres en el texto y dos fotos navegando, iguales en los dos idiomas', () => {
  const es = c.getSedeContenido('la-paz', 'es').pangas;
  const en = c.getSedeContenido('la-paz', 'en').pangas;
  for (const p of [es, en]) {
    assert.ok(p.titulo && p.frase && p.y);
    assert.ok(p.flota.src.startsWith('/photos/') && p.flota.alt && p.flota.ancho > p.flota.alto, 'la flota es horizontal');
    assert.ok(p.texto.includes('{nombres}'), 'el párrafo nombra las pangas');
    assert.equal(p.fotos.length, 2);
    assert.ok(p.fotos.every((f) => f.src.startsWith('/photos/') && f.alt && f.pie));
    assert.ok(!/[—–]/.test(JSON.stringify(p)));
  }
  assert.deepEqual(es.nombres, ['Don Piry', 'Volador', 'Dream', 'Escoria del Mar', 'Esperanzas', 'Storm', 'Volador III']);
  assert.deepEqual(es.nombres, en.nombres, 'los nombres no se traducen');
  assert.equal(es.flota.src, en.flota.src);
  assert.deepEqual(es.fotos.map((f) => f.src), en.fotos.map((f) => f.src));
  assert.equal(c.getSedeContenido('la-paz', 'es').hero.marca, undefined, 'el héroe vuelve a ser el de video');
});

test('el héroe de La Paz se encuadra a la izquierda en celular, en los dos idiomas', () => {
  for (const lang of ['es', 'en']) assert.equal(c.getSedeContenido('la-paz', lang).hero.posicionImagenMovil, '75% 50%');
});
