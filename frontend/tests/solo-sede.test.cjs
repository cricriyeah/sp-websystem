/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SOLO_SEDE_TEST_OUT, 'lib/solo-sede.js'));

const decidir = (pathname, { search = '', cookie, idiomaPreferido = 'es' } = {}) =>
  s.decidirSoloSede({ pathname, search, cookie, idiomaPreferido });

const guarda = (destino, sede) => ({ tipo: 'redirigir', destino, cookie: { guardar: sede } });
const sigue = { tipo: 'seguir' };

test('los tres links cortos llevan a su sede y guardan el modo', () => {
  assert.deepEqual(decidir('/lapaz'), guarda('/es/sede/la-paz', 'la-paz'));
  assert.deepEqual(decidir('/laventana'), guarda('/es/sede/la-ventana', 'la-ventana'));
  assert.deepEqual(decidir('/puertochale'), guarda('/es/sede/puerto-chale', 'puerto-chale'));
});

test('el link corto toma el idioma del navegador, o el de la ruta si lo trae', () => {
  assert.deepEqual(decidir('/lapaz', { idiomaPreferido: 'en' }), guarda('/en/sede/la-paz', 'la-paz'));
  assert.deepEqual(decidir('/en/lapaz'), guarda('/en/sede/la-paz', 'la-paz'));
  assert.deepEqual(decidir('/es/lapaz', { idiomaPreferido: 'en' }), guarda('/es/sede/la-paz', 'la-paz'));
});

test('mayúsculas y diagonal final no cambian el link corto', () => {
  assert.deepEqual(decidir('/LaPaz/'), guarda('/es/sede/la-paz', 'la-paz'));
});

test('el link corto conserva la query (el ?ref= de la vendedora)', () => {
  assert.deepEqual(decidir('/lapaz', { search: '?ref=maria' }), guarda('/es/sede/la-paz?ref=maria', 'la-paz'));
});

test('un link corto pisa el modo de otra sede', () => {
  assert.deepEqual(decidir('/laventana', { cookie: 'la-paz' }), guarda('/es/sede/la-ventana', 'la-ventana'));
});

test('/hub borra el modo y va a la portada', () => {
  assert.deepEqual(decidir('/hub', { cookie: 'la-paz' }), { tipo: 'redirigir', destino: '/es', cookie: 'borrar' });
  assert.deepEqual(decidir('/en/hub'), { tipo: 'redirigir', destino: '/en', cookie: 'borrar' });
});

test('con el modo puesto, la portada y «Sobre nosotros» llevan a la sede', () => {
  const aLaPaz = (destino) => ({ tipo: 'redirigir', destino });
  assert.deepEqual(decidir('/', { cookie: 'la-paz' }), aLaPaz('/es/sede/la-paz'));
  assert.deepEqual(decidir('/es', { cookie: 'la-paz' }), aLaPaz('/es/sede/la-paz'));
  assert.deepEqual(decidir('/en/', { cookie: 'la-paz' }), aLaPaz('/en/sede/la-paz'));
  assert.deepEqual(decidir('/es/nosotros', { cookie: 'la-paz' }), aLaPaz('/es/sede/la-paz'));
  assert.deepEqual(decidir('/es', { cookie: 'la-paz', search: '?ref=ana' }), aLaPaz('/es/sede/la-paz?ref=ana'));
});

test('sin modo, la portada y «Sobre nosotros» no se tocan', () => {
  assert.deepEqual(decidir('/'), sigue);
  assert.deepEqual(decidir('/es'), sigue);
  assert.deepEqual(decidir('/es/nosotros'), sigue);
});

test('una cookie que no es de una sede se ignora', () => {
  assert.deepEqual(decidir('/es', { cookie: 'los-cabos' }), sigue);
  assert.deepEqual(decidir('/es', { cookie: '../admin' }), sigue);
  assert.deepEqual(decidir('/es', { cookie: '' }), sigue);
});

test('con el modo puesto, el resto del sitio no se toca', () => {
  for (const ruta of [
    '/es/sede/la-paz',
    '/es/sede/la-ventana',
    '/es/sede/la-paz/paquete/pesca-traslado',
    '/es/servicio/sal-y-sol/pesca-deportiva',
    '/es/reservar',
    '/es/traslados',
    '/es/privacidad',
    '/es/deslinde',
    '/es/catalogo',
    '/es/lo-que-sea',
    '/nosotros',
  ]) {
    assert.deepEqual(decidir(ruta, { cookie: 'la-paz', search: '?paso=pago' }), sigue, ruta);
  }
});

test('ninguna redirección vuelve a caer en otra (no hay cadenas ni bucles)', () => {
  const entradas = ['/lapaz', '/laventana', '/puertochale', '/en/lapaz', '/hub', '/', '/es', '/en', '/es/nosotros'];
  for (const cookie of [undefined, 'la-paz', 'la-ventana']) {
    for (const ruta of entradas) {
      const primera = decidir(ruta, { cookie });
      if (primera.tipo !== 'redirigir') continue;
      const nuevaCookie = primera.cookie === 'borrar' ? undefined : primera.cookie?.guardar ?? cookie;
      const segunda = decidir(primera.destino, { cookie: nuevaCookie });
      assert.deepEqual(segunda, sigue, `${ruta} (cookie ${cookie}) → ${primera.destino}`);
    }
  }
});

test('el script del navegador solo acepta las sedes del modo', () => {
  for (const sede of s.SEDES_SOLO) assert.ok(s.SCRIPT_SOLO_SEDE.includes(`"${sede}"`), sede);
  assert.ok(s.SCRIPT_SOLO_SEDE.includes(s.COOKIE_SOLO_SEDE));
});
