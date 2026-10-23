/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.IDIOMA_CATALOGO_TEST_OUT, 'lib/idioma-catalogo.js'));

const servicio = { nombre: 'Pesca con mosca', nombre_en: 'Fly fishing', descripcion: 'Un día', descripcion_en: 'A day' };

test('enIdioma: en español no cambia nada', () => {
  assert.equal(m.enIdioma(servicio, 'es'), servicio);
});

test('enIdioma: en inglés usa nombre_en y descripcion_en', () => {
  const r = m.enIdioma(servicio, 'en');
  assert.equal(r.nombre, 'Fly fishing');
  assert.equal(r.descripcion, 'A day');
});

test('enIdioma: sin inglés (vacío, espacios o ausente) se queda el español', () => {
  assert.equal(m.enIdioma({ ...servicio, nombre_en: '  ', descripcion_en: '' }, 'en').nombre, 'Pesca con mosca');
  assert.equal(m.enIdioma({ nombre: 'Hotel', descripcion: 'x' }, 'en').descripcion, 'x');
});

test('enIdioma: no inventa descripcion donde el objeto no la trae', () => {
  assert.equal('descripcion' in m.enIdioma({ nombre: 'Traslados', nombre_en: 'Transfers' }, 'en'), false);
});

test('paqueteEnIdioma: traduce el paquete y sus servicios', () => {
  const paquete = { nombre: 'Paquete 5 noches', nombre_en: '5-night package', descripcion: 'd', servicios_asociados: [{ orden: 1, servicio }] };
  const r = m.paqueteEnIdioma(paquete, 'en');
  assert.equal(r.nombre, '5-night package');
  assert.equal(r.servicios_asociados[0].servicio.nombre, 'Fly fishing');
  assert.equal(r.servicios_asociados[0].orden, 1);
  assert.equal(m.paqueteEnIdioma(paquete, 'es'), paquete);
});

test('enIdioma: traduce la ficha y los nombres de los extras, con el español de respaldo', () => {
  const pesca = {
    nombre: 'Pesca', duracion: 'Día completo', duracion_en: 'Full day', punto_salida: 'Marina La Costa', punto_salida_en: '',
    personalizaciones: [{ nombre: 'Licencia de pesca', nombre_en: 'Fishing license' }, { nombre: 'Carnada', nombre_en: '' }],
  };
  const r = m.enIdioma(pesca, 'en');
  assert.equal(r.duracion, 'Full day');
  assert.equal(r.punto_salida, 'Marina La Costa');
  assert.deepEqual(r.personalizaciones.map((e) => e.nombre), ['Fishing license', 'Carnada']);
  assert.equal('duracion' in m.enIdioma({ nombre: 'x' }, 'en'), false);
});
