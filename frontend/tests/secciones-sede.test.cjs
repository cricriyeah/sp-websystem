/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SECCIONES_TEST_OUT, 'lib/secciones-sede.js'));

const foto = { ancho: 1448, alto: 1086 };
const base = { servicios: [{}], paquetes: [], resenas: [], fotos: [], faq: [], temporadas: null, dia: undefined, conocenos: undefined };
const ids = (entrada) => s.seccionesDeSede({ ...base, ...entrada }).map((x) => x.id);
const reservar = (entrada) => s.seccionesDeSede({ ...base, ...entrada }).find((x) => x.id === 'reservar');

test('las pangas van justo después del héroe, antes de lo que se reserva, y no salen en el menú', () => {
  assert.deepEqual(ids({ pangas: [{}] }).slice(0, 3), ['hero', 'pangas', 'reservar']);
  assert.ok(!ids({ pangas: [] }).includes('pangas'));
  assert.ok(!ids({}).includes('pangas'));
  assert.deepEqual(s.enlacesDeSede(['hero', 'pangas', 'reservar']).map((e) => e.claveNav), ['reservar']);
  const fondos = s.fondosDeSecciones(['hero', 'pangas', 'reservar']);
  assert.notEqual(fondos.pangas, fondos.reservar, 'dos bandas seguidas nunca con el mismo tono');
});

test('catálogo caído: ambas listas null', () => {
  assert.deepEqual(reservar({ servicios: null, paquetes: null }), { id: 'reservar', estado: 'catalogo_caido' });
});

test('catálogo vacío: ambas listas vacías', () => {
  assert.deepEqual(reservar({ servicios: [], paquetes: [] }), { id: 'reservar', estado: 'vacio' });
});

test('con algo que reservar: normal', () => {
  assert.deepEqual(reservar({ servicios: [], paquetes: [{}] }), { id: 'reservar', estado: 'normal' });
});

test('sin contenido no hay sección: lo mínimo es héroe, reservar y tranquilidad', () => {
  assert.deepEqual(ids({}), ['hero', 'reservar', 'tranquilidad']);
});

test('sin reseñas confirmadas no hay opiniones (ni sustituto)', () => {
  assert.deepEqual(ids({ resenas: [{ confirmada: false }] }), ['hero', 'reservar', 'tranquilidad']);
  assert.ok(ids({ resenas: [{ confirmada: true }] }).includes('opiniones'));
});

test('galería solo con 3 fotos aptas', () => {
  assert.ok(!ids({ fotos: [foto, foto, { ancho: 300, alto: 200 }] }).includes('galeria'));
  assert.ok(ids({ fotos: [foto, foto, foto] }).includes('galeria'));
});

test('orden fijo de la sede, con todo', () => {
  assert.deepEqual(
    ids({ paquetes: [{}], dia: [{}], conocenos: [{}], fotos: [foto, foto, foto], temporadas: [{}], resenas: [{ confirmada: true }], faq: [{}] }),
    ['hero', 'reservar', 'paquetes', 'dia', 'tranquilidad', 'opiniones', 'conocenos', 'galeria', 'temporadas', 'preguntas'],
  );
});

test('paquetes y día solo si hay contenido real: sin paquetes o sin momentos no se pintan', () => {
  assert.ok(!ids({ paquetes: [] }).includes('paquetes'));
  assert.ok(!ids({ paquetes: null }).includes('paquetes'));
  assert.ok(ids({ paquetes: [{}] }).includes('paquetes'));
  assert.ok(!ids({ dia: [] }).includes('dia'));
  assert.ok(!ids({ dia: undefined }).includes('dia'));
  assert.ok(ids({ dia: [{}] }).includes('dia'));
});

test('conócenos solo con fotos, entre tranquilidad y la galería, y fuera del menú', () => {
  assert.ok(!ids({ conocenos: [] }).includes('conocenos'));
  assert.ok(!ids({ conocenos: undefined }).includes('conocenos'));
  assert.deepEqual(ids({ conocenos: [{}], fotos: [foto, foto, foto] }), ['hero', 'reservar', 'tranquilidad', 'conocenos', 'galeria']);
  assert.deepEqual(s.enlacesDeSede(['hero', 'reservar', 'tranquilidad', 'conocenos', 'galeria']).map((e) => e.claveNav), ['reservar', 'galeria']);
  const fondos = s.fondosDeSecciones(['hero', 'reservar', 'tranquilidad', 'conocenos', 'galeria']);
  assert.equal(fondos.conocenos, 'blanco');
  assert.equal(fondos.galeria, 'cafe-bruma');
});

test('enlaces del menú: un ancla por sección navegable, sin héroe, paquetes, día ni tranquilidad', () => {
  assert.deepEqual(s.enlacesDeSede(['hero', 'reservar', 'paquetes', 'dia', 'tranquilidad', 'preguntas']), [
    { ancla: '#reservar', claveNav: 'reservar' },
    { ancla: '#preguntas', claveNav: 'preguntas' },
  ]);
  assert.equal(s.ANCLA_DE.galeria, 'galeria');
});

test('fondos por posición: reservar en blanco, tranquilidad en la banda negra, nunca dos iguales seguidos', () => {
  const pintadas = ['hero', 'reservar', 'tranquilidad', 'galeria', 'temporadas', 'opiniones', 'preguntas'];
  const fondos = s.fondosDeSecciones(pintadas);
  assert.equal(fondos.hero, undefined);
  assert.equal(fondos.reservar, 'blanco');
  assert.equal(fondos.tranquilidad, 'tinta');
  const orden = pintadas.slice(1).map((id) => fondos[id]);
  orden.forEach((f, i) => { if (i) assert.notEqual(f, orden[i - 1]); });
});

test('fondos sobre las secciones pintadas: la banda negra solo la lleva tranquilidad', () => {
  const fondos = s.fondosDeSecciones(['hero', 'reservar', 'galeria', 'temporadas', 'preguntas']);
  assert.deepEqual(['reservar', 'galeria', 'temporadas', 'preguntas'].map((id) => fondos[id]), ['blanco', 'cafe-bruma', 'blanco', 'cafe-bruma']);
  for (const f of Object.values(fondos)) assert.notEqual(f, 'tinta');
});

test('anclas fijas del hub', () => {
  assert.deepEqual(s.ANCLA_HUB, { mapa: 'mapa', sedes: 'sedes', comoFunciona: 'como-funciona', empresas: 'empresas' });
});
