/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SOLO_SEDE_TEST_OUT, 'lib/solo-sede.js'));

const decidir = (pathname, { search = '', cookie, idiomaPreferido = 'es', esCargaDePagina } = {}) =>
  s.decidirSoloSede({ pathname, search, cookie, idiomaPreferido: () => idiomaPreferido, esCargaDePagina });

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
  assert.deepEqual(decidir('/nosotros', { cookie: 'la-paz', idiomaPreferido: 'en' }), aLaPaz('/en/sede/la-paz'));
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

test('con el modo puesto, el resto del sitio no redirige', () => {
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
  ]) {
    assert.equal(decidir(ruta, { cookie: 'la-paz', search: '?paso=pago' }).tipo, 'seguir', ruta);
  }
});

test('ninguna redirección vuelve a caer en otra (no hay cadenas ni bucles)', () => {
  const entradas = ['/lapaz', '/laventana', '/puertochale', '/en/lapaz', '/hub', '/', '/es', '/en', '/es/nosotros', '/nosotros'];
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

test('los nombres heredados de Object no son links cortos', () => {
  for (const ruta of ['/constructor', '/__proto__', '/es/constructor', '/tostring', '/hasownproperty']) {
    assert.deepEqual(decidir(ruta), sigue, ruta);
    assert.deepEqual(decidir(ruta, { cookie: 'la-paz' }), sigue, ruta);
  }
});

test('el idioma del navegador solo se calcula si la ruta no lo trae', () => {
  let veces = 0;
  const contar = () => { veces += 1; return 'es'; };
  for (const ruta of ['/es/sede/la-paz', '/es/reservar', '/en', '/es/nosotros', '/es/lapaz']) {
    s.decidirSoloSede({ pathname: ruta, search: '', cookie: 'la-paz', idiomaPreferido: contar });
  }
  assert.equal(veces, 0);
  s.decidirSoloSede({ pathname: '/lapaz', search: '', cookie: undefined, idiomaPreferido: contar });
  assert.equal(veces, 1);
});

const pasaA = (sede) => ({ tipo: 'seguir', cookie: { guardar: sede } });

test('con el modo puesto, abrir otra sede pasa el modo a esa', () => {
  assert.deepEqual(decidir('/es/sede/la-ventana', { cookie: 'la-paz' }), pasaA('la-ventana'));
  assert.deepEqual(decidir('/en/sede/puerto-chale/paquete/ballenas', { cookie: 'la-paz' }), pasaA('puerto-chale'));
  assert.deepEqual(decidir('/es/sede/la-paz', { cookie: 'la-paz' }), sigue);
});

test('el checkout directo de otra empresa pasa el modo a su sede (el link de la vendedora)', () => {
  const cookie = 'la-paz';
  assert.deepEqual(decidir('/es/reservar', { cookie, search: '?servicio=kite&empresa=la-ventana-travel&moneda=MXN' }), pasaA('la-ventana'));
  assert.deepEqual(decidir('/es/reservar', { cookie, search: '?paquete=ballenas&sede=puerto-chale' }), pasaA('puerto-chale'));
  assert.deepEqual(decidir('/es/reservar', { cookie, search: '?paquete=x&paquete_empresa=piratas-adventures' }), pasaA('puerto-chale'));
  assert.deepEqual(decidir('/es/traslados', { cookie: 'la-ventana', search: '?empresa=transporte-la-paz' }), pasaA('la-paz'));
  assert.deepEqual(decidir('/es/servicio/la-ventana-travel/kite', { cookie }), pasaA('la-ventana'));
  // `?sede=` manda sobre la empresa, como en la página.
  assert.deepEqual(decidir('/es/servicio/sal-y-sol/pesca-deportiva', { cookie: 'la-ventana', search: '?sede=la-paz' }), pasaA('la-paz'));
});

test('la página de la misma sede, una sin sede o un dato desconocido no cambian el modo', () => {
  const cookie = 'la-paz';
  for (const [ruta, search] of [
    ['/es/reservar', '?servicio=pesca-deportiva&empresa=sal-y-sol'],
    ['/es/reservar', ''],
    ['/es/reservar', '?empresa=no-existe'],
    ['/es/reservar', '?sede=los-cabos'],
    ['/es/traslados', ''],
    ['/es/servicio/no-existe/algo', ''],
    ['/es/sede/no-existe', ''],
    ['/es/privacidad', '?empresa=la-ventana-travel'],
  ]) {
    assert.deepEqual(decidir(ruta, { cookie, search }), sigue, ruta + search);
  }
});

test('sin modo, abrir una sede o un checkout no lo enciende', () => {
  assert.deepEqual(decidir('/es/sede/la-ventana'), sigue);
  assert.deepEqual(decidir('/es/reservar', { search: '?empresa=la-ventana-travel' }), sigue);
});

test('una petición por fetch (el prefetch de Next) no cambia el modo; las redirecciones siguen', () => {
  assert.deepEqual(decidir('/es/sede/la-ventana', { cookie: 'la-paz', esCargaDePagina: false }), sigue);
  assert.deepEqual(decidir('/es', { cookie: 'la-paz', esCargaDePagina: false }), { tipo: 'redirigir', destino: '/es/sede/la-paz' });
});

test('el script del navegador lee la cookie igual que leerSoloSedeCliente', () => {
  const cuerpo = { dataset: {} };
  const correr = (cookie) => {
    cuerpo.dataset = {};
    new Function('document', s.SCRIPT_SOLO_SEDE)({ cookie, body: cuerpo });
    return cuerpo.dataset.soloSede;
  };
  assert.equal(correr('a=1; sbe_solo_sede=la-ventana; b=2'), 'la-ventana');
  assert.equal(correr('sbe_solo_sede=la-paz'), 'la-paz');
  assert.equal(correr('sbe_solo_sede=los-cabos'), undefined);
  assert.equal(correr('otro_sbe_solo_sede=la-paz'), undefined);
});
