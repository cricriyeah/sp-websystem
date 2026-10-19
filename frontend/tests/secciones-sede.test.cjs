/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SECCIONES_TEST_OUT, 'lib/secciones-sede.js'));

const foto = { ancho: 1448, alto: 1086 };
const base = { servicios: [{}], paquetes: [], resenas: [], fotos: [], faq: [], temporadas: null };
const ids = (entrada) => s.seccionesDeSede({ ...base, ...entrada }).map((x) => x.id);
const reservar = (entrada) => s.seccionesDeSede({ ...base, ...entrada }).find((x) => x.id === 'reservar');

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
    ids({ fotos: [foto, foto, foto], temporadas: [{}], resenas: [{ confirmada: true }], faq: [{}] }),
    ['hero', 'reservar', 'tranquilidad', 'galeria', 'temporadas', 'opiniones', 'preguntas'],
  );
});

test('enlaces del menú: un ancla por sección navegable, sin héroe ni tranquilidad', () => {
  assert.deepEqual(s.enlacesDeSede(['hero', 'reservar', 'tranquilidad', 'preguntas']), [
    { ancla: '#reservar', claveNav: 'reservar' },
    { ancla: '#preguntas', claveNav: 'preguntas' },
  ]);
  assert.equal(s.ANCLA_DE.galeria, 'galeria');
});

test('fondos por posición: reservar en arena, tranquilidad en café bruma, nunca dos iguales seguidos', () => {
  const pintadas = ['hero', 'reservar', 'tranquilidad', 'galeria', 'temporadas', 'opiniones', 'preguntas'];
  const fondos = s.fondosDeSecciones(pintadas);
  assert.equal(fondos.reservar.fondo, 'arena');
  assert.equal(fondos.tranquilidad.fondo, 'cafe-bruma');
  const orden = pintadas.slice(1).map((id) => fondos[id].fondo);
  orden.forEach((f, i) => { if (i) assert.notEqual(f, orden[i - 1]); });
});

test('fondos sobre las secciones pintadas: sin tranquilidad, la galería no repite el de reservar', () => {
  const fondos = s.fondosDeSecciones(['hero', 'reservar', 'galeria', 'temporadas', 'preguntas']);
  assert.deepEqual(['reservar', 'galeria', 'temporadas', 'preguntas'].map((id) => fondos[id].fondo), ['arena', 'blanco', 'arena', 'blanco']);
});

test('borde arriba en toda banda salvo la primera', () => {
  const fondos = s.fondosDeSecciones(['hero', 'reservar', 'preguntas']);
  assert.equal(fondos.hero.borde, false);
  assert.equal(fondos.reservar.borde, true);
  assert.equal(fondos.preguntas.borde, true);
});

test('anclas fijas del hub', () => {
  assert.deepEqual(s.ANCLA_HUB, { mapa: 'mapa', sedes: 'sedes', comoFunciona: 'como-funciona', empresas: 'empresas' });
});
