/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const a = require(path.join(process.env.ATRIBUCION_TEST_OUT, 'lib/atribucion.js'));

const AHORA = new Date('2026-11-11T18:00:00Z');
const visita = (o) => a.atribucionDeVisita({
  search: '', referrer: '', hostPropio: 'www.salysoltours.com', ruta: '/es/sede/la-paz', ahora: AHORA, hayGuardada: false, ...o,
});

test('un anuncio guarda sus parámetros, la página de llegada y la hora', () => {
  const d = visita({ search: '?utm_source=facebook&utm_campaign=orcas&fbclid=abc&otro=x', referrer: 'https://l.facebook.com/' });
  assert.deepEqual(d, {
    utm_source: 'facebook', utm_campaign: 'orcas', fbclid: 'abc', referrer: 'l.facebook.com',
    landing: '/es/sede/la-paz', capturado_en: AHORA.toISOString(),
  });
});

test('un enlace nuevo con parámetros pisa al anterior', () => {
  assert.equal(visita({ search: '?gclid=g1', hayGuardada: true }).gclid, 'g1');
});

test('una visita sin parámetros no borra lo guardado', () => {
  assert.equal(visita({ referrer: 'https://www.google.com/', hayGuardada: true }), null);
});

test('sin nada guardado, se anota de qué sitio venía', () => {
  assert.equal(visita({ referrer: 'https://www.tripadvisor.com/x' }).referrer, 'tripadvisor.com');
});

test('navegar dentro del propio sitio o entrar directo no guarda nada', () => {
  assert.equal(visita({ referrer: 'https://salysoltours.com/es' }), null);
  assert.equal(visita({}), null);
  assert.equal(a.dominioDeOrigen('no es url', 'x.com'), '');
});
