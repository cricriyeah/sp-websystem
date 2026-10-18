/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const o = require(path.join(process.env.ORIGEN_TEST_OUT, 'lib/origen.js'));

test('sin origen explícito vuelve a la sede', () => {
  assert.equal(o.hrefDeOrigen({ lang: 'es', sedeSlug: 'la-paz' }), '/es/sede/la-paz');
});

test('sin origen ni sede vuelve a la portada', () => {
  assert.equal(o.hrefDeOrigen({ lang: 'en' }), '/en');
});

test('origen portada manda a la portada aunque haya sede', () => {
  assert.equal(o.hrefDeOrigen({ lang: 'es', origen: 'portada', sedeSlug: 'la-paz' }), '/es');
});

test('origen servicio manda a la página del servicio', () => {
  assert.equal(
    o.hrefDeOrigen({ lang: 'es', origen: 'servicio', sedeSlug: 'la-paz', rutaServicio: 'servicio/sal-y-sol/pesca' }),
    '/es/servicio/sal-y-sol/pesca',
  );
});

test('origen servicio sin ruta cae en la sede', () => {
  assert.equal(o.hrefDeOrigen({ lang: 'es', origen: 'servicio', sedeSlug: 'la-paz' }), '/es/sede/la-paz');
});

test('un origen desconocido se ignora', () => {
  assert.equal(o.hrefDeOrigen({ lang: 'es', origen: 'http://malo.example', sedeSlug: 'la-paz' }), '/es/sede/la-paz');
  assert.equal(o.origenValido('sede'), 'sede');
  assert.equal(o.origenValido('otro'), null);
});
